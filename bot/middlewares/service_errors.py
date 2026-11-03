"""Keep a customer's input and access when generation or storage is unavailable."""
import logging
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from bot.services.ai_service import AIUnavailable
from bot.services.fulfillment import PurchaseRequired, recover_pending

logger = logging.getLogger(__name__)


class ServiceErrorsMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if not isinstance(event, CallbackQuery) and (getattr(event, "text", "") or "").strip().lower() in ("/stop", "/notifications_on"):
            from bot.services.notifications import set_muted
            off = event.text.strip().lower() == "/stop"
            await set_muted("tg", event.from_user.id, off)
            await event.answer("Уведомления отключены. Ответы на ваши запросы и сообщения об оплате останутся. Включить: /notifications_on"
                               if off else "Уведомления включены. Отключить: /stop")
            return
        state = data.get("state")
        old_state = await state.get_state() if state else None
        old_data = await state.get_data() if state else {}
        session, user = data.get("session"), data.get("user")
        lang = data.get("lang", "ru")
        try:
            if session and user:
                await recover_pending(session, user.id)
            return await handler(event, data)
        except (AIUnavailable, PurchaseRequired, RedisError, SQLAlchemyError) as exc:
            logger.warning("Service unavailable: %s", type(exc).__name__)
            if session:
                await session.rollback()
            if state and not isinstance(exc, RedisError):
                await state.set_state(old_state)
                await state.set_data(old_data)
            if isinstance(exc, PurchaseRequired):
                from bot.keyboards.main import payment_method_keyboard
                from config import PRODUCTS
                product = PRODUCTS[str(exc)]
                text = {"ru": "Для нового разбора нужен доступ. Выберите способ оплаты; готовые результаты доступны в «Мои разборы».",
                        "en": "A new reading requires access. Choose payment; completed readings remain in My Readings.",
                        "fa": "برای تفسیر جدید دسترسی لازم است. نتایج قبلی در تاریخچه موجود است.",
                        "tr": "Yeni okuma için erişim gerekir. Önceki sonuçlar geçmişinizde durur."}.get(lang)
                kb = payment_method_keyboard(str(exc), product["price_rub"], product["price_stars"], lang)
            else:
                text = {"ru": "Не удалось завершить ответ. Повторите запрос чуть позже. Неудачная генерация не списывает разбор. Если ответ уже был готов, он сохранён в «Мои разборы».",
                        "en": "The answer could not be completed. Please retry shortly. Failed generation does not use your reading. Completed answers are saved in My Readings.",
                        "fa": "پاسخ کامل نشد. کمی بعد دوباره تلاش کنید. تولید ناموفق از سهم شما کم نمی‌کند؛ پاسخ آماده در تاریخچه ذخیره می‌شود.",
                        "tr": "Yanıt tamamlanamadı. Biraz sonra tekrar deneyin. Başarısız üretim hakkınızı tüketmez; hazır yanıt geçmişe kaydedilir."}.get(lang)
                from bot.keyboards.main import back_to_main
                kb = back_to_main()
            message = event.message if isinstance(event, CallbackQuery) else event
            if isinstance(event, CallbackQuery):
                await event.answer()
            await message.answer(text or "Please try again later.", reply_markup=kb, parse_mode=None)
