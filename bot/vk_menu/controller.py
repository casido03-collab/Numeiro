"""Human-readable VK conversations with explicit purchase and operator handoff."""
import json
import re
import time
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select, func, update
from config import PRODUCTS, VIP_PLAN, settings
from bot.models.user import User, UserReport
from bot.models.vk import VKAccount, VKOrder, VKOutbox, VKReferralReward
from bot.vk_menu import keyboards as kb, readings, offers
from bot.vk_menu.payments import checkout, check_order
from bot.services.limits import can_use_product, get_vip_limits_summary, is_vip, add_credit, activate_vip
from bot.services.cache import get_redis
from bot.services.fulfillment import recover_pending, PurchaseRequired
from bot.services.ai_service import AIUnavailable
from bot.services.clarification import clarify, is_open, ClarificationUnavailable
from bot.services.reports_service import get_report_by_id, save_report
from bot.utils import parse_birth_date

COMMANDS = {"начать": "menu", "старт": "menu", "меню": "menu", "/start": "menu", "/menu": "menu",
            "отмена": "menu", "/cancel": "menu", "/help": "help", "помощь": "help",
            "поддержка": "support", "техподдержка": "support", "/support": "support",
            "вернуться к боту": "resume", "/bot": "resume", "/stop": "mute", "/notifications_on": "unmute",
            "/new_context": "new_context", "/last_reading": "last", "/new_question": "product:personal_question"}


def command(message):
    raw = message.get("payload")
    try:
        payload = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(payload, dict) and isinstance(payload.get("a"), str):
            return payload["a"][:180]
    except (ValueError, TypeError):
        pass
    text = (message.get("text") or "").strip()
    return kb.LABEL_COMMANDS.get(text) or COMMANDS.get(text.lower(), "")


async def account_for(session, api, uid, ref=""):
    account = await session.get(VKAccount, uid)
    if account:
        return account, await session.get(User, account.user_id)
    first_name = "друг"
    try:
        users = await api.users.get(user_ids=[uid])
        if users:
            first_name = users[0].first_name or first_name
    except Exception:
        pass
    # Existing consultations keep their data and remain reachable from the profile.
    from bot.vk_dialog.session_manager import get_profile
    old = await get_profile(uid)
    birth = old.get("birth_date")
    birth = birth if parse_birth_date(birth or "") else None
    user = User(telegram_id=None, first_name=old.get("name") or first_name, birth_date=birth)
    session.add(user)
    await session.flush()
    referrer = None
    if re.fullmatch(r"ref_\d+", ref or ""):
        candidate = int(ref[4:])
        if candidate != uid and await session.get(VKAccount, candidate):
            referrer = candidate
    account = VKAccount(vk_id=uid, user_id=user.id, state="menu", data={}, referrer_id=referrer)
    session.add(account)
    if old.get("last_paid_result"):
        await save_report(session, user.id, "legacy_vk", "Прежняя консультация Аиши", old["last_paid_result"], {"legacy": True})
    await session.commit()
    return account, user


def state(account, value, **data):
    account.state, account.data = value, data


async def show_menu(account, reply, welcome=False):
    state(account, "menu")
    if welcome:
        await reply.send("💜 Добро пожаловать к Бабушке Аише.\n\nЯ цифровой помощник: помогу посмотреть на ваш вопрос через символы, числа и карты — без обещаний предсказать будущее.\n\n🌙 Бесплатно: гороскоп дня и одна «Энергия дня» в день.\n🔮 Персональные разборы оплачиваются отдельно. Состав и стоимость — внутри каждой услуги.\n\nВыберите раздел внизу. Для живого общения с владельцем — «Техподдержка».",
                         kb.home(), settings.vk_menu_cover or None)
    else:
        await reply.send("🔮 Меню Аиши\nВыберите услугу, бесплатный прогноз или сохранённый разбор.", kb.home())
    await show_catalog(account, reply)


async def show_catalog(account, reply, page=0):
    page = max(0, min(page, len(kb.CATALOG_PAGES)-1))
    state(account, "menu")
    lines = []
    for product in kb.CATALOG_PAGES[page]:
        if product == "vip":
            lines.append(f"💎 VIP на {VIP_PLAN['duration_days']} дней")
        else:
            lines.append(f"{kb.ICONS[product]} {PRODUCTS[product]['name']}")
    text = (f"🔮 Услуги Аиши · {page+1}/{len(kb.CATALOG_PAGES)}\n\n"+"\n".join(lines)+
            "\n\nВыберите услугу — покажу, что входит и сколько стоит.")
    await reply.send(text, kb.catalog(page))


def offer(product):
    return offers.product_offer(product)


async def show_result(reply, report):
    rows = []
    meta = report.metadata_json or {}
    if report.report_type == "personal_question" and not meta.get("parent_report_id"):
        if meta.get("clarification_report_id") or is_open(report):
            label = "💬 Открыть уточнение" if meta.get("clarification_report_id") else "💬 Уточнение включено · 24 часа"
            rows.append([kb.button(label, f"clarify:{report.id}", "positive")])
    rows.append([kb.button("📚 Мои разборы", "history", "secondary"), kb.button("🔮 Меню", "menu", "secondary")])
    await reply.send(f"{report.title}\n\n{report.content}", kb.keyboard(rows), card_key=meta.get("card_key"))


async def begin(account, user, product, reply):
    if not user.birth_date:
        state(account, "birth", resume=product)
        await reply.send("🌙 Введите дату рождения в формате ДД.ММ.ГГГГ — например, 15.03.1990.\nОна нужна для вашего разбора и сохранится в профиле. Оплата пока не требуется.", kb.back())
        return
    state(account, "inputs", product=product)
    if product == "personal_question":
        await reply.send("🔮 Что хотите разобрать?\nНапишите один вопрос и немного контекста — от 10 до 2000 символов.\nЗа 29 ₽ вы получите законченный ответ и одно уточнение в течение 24 часов. Сначала покажу подтверждение заказа.", kb.back())
    elif product in ("mini_reading", "weekly_report"):
        await reply.send("✨ Какая сфера сейчас важнее?", kb.choices(readings.SPHERE_NAMES.items(), "sphere"))
    elif product == "compatibility":
        state(account, "partner", product=product)
        await reply.send("💞 Ваша дата уже сохранена. Напишите дату рождения второго человека: ДД.ММ.ГГГГ.", kb.back())
    elif product == "date_selection":
        await reply.send("📆 Для какого события подбираем даты?", kb.choices([(k,v) for k,v in readings.EVENT_NAMES.items() if k not in ("medical","investment")], "event"))
    # Matrix and tarot are prepared by the caller after the birth-date step.


async def prepare(session, account, user, event, reply):
    product = account.data["product"]
    if product == "tarot_card":
        reports = (await session.scalars(select(UserReport).where(UserReport.user_id==user.id,
            UserReport.report_type=="tarot_card").order_by(UserReport.id.desc()).limit(20))).all()
        previous = next((r for r in reports if (r.metadata_json or {}).get("date")==readings.today().isoformat()), None)
        if previous:
            state(account, "menu")
            await reply.send("Ваша карта на сегодня уже готова. Открываю её без нового списания 💜")
            await show_result(reply, previous)
            return
    order_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"vk-order:{event.event_key}"))
    order = await session.get(VKOrder, order_id)
    if order is None:
        details = await readings.build_details(session, user, product, account.data, event.event_key)
        previous = await readings.cached_report(session, user.id, product, details)
        if previous:
            state(account, "menu")
            await reply.send("Этот разбор уже готов. Открываю его без нового списания 💜")
            await show_result(reply, previous)
            return
        order = VKOrder(id=order_id, user_id=user.id, vk_id=account.vk_id, product=product,
                        amount=PRODUCTS[product]["price_rub"], details=details)
        session.add(order)
    state(account, "ready", order_id=order.id)
    await session.commit()
    await show_order(session, account, order, reply)


async def show_order(session, account, order, reply):
    if order.report_id:
        await show_result(reply, await session.get(UserReport, order.report_id))
        return
    available = order.product != "vip" and await can_use_product(order.user_id, order.product)
    text = vip_text() if order.product == "vip" else offer(order.product)
    if order.product != "vip":
        context = order.details["context"]
        extra = []
        for key,label in (("question","Ваш вопрос"),("birth_date","Дата рождения"),("sphere","Сфера"),
                          ("partner_birth","Дата партнёра"),("relation_type","Отношения"),("event","Событие"),
                          ("date","Дата карты"),("week_start","Неделя с"),("week_end","По"),
                          ("period_start","Начало периода"),("period_end","Конец периода"),("available_days","Дни")):
            if key in context:
                value = {"all":"любые", "workdays":"будни", "weekends":"выходные"}.get(str(context[key]), context[key])
                extra.append(f"{label}: {value}")
        text += "\n\n"+"\n".join(extra)
    rows = []
    if available:
        text += "\n\n✅ У вас есть доступ. Будет использован один разбор из VIP или купленного остатка; новая оплата не нужна."
        rows.append([kb.button("✨ Получить разбор", f"run:{order.id}", "positive")])
    elif order.status == "pending":
        text += "\n\nСчёт уже создан. Не оплачивайте его повторно, если деньги списались: нажмите «Проверить оплату»."
        rows.extend([[kb.link(f"💳 Оплатить {order.amount} ₽", order.checkout_url)],
                     [kb.button("✅ Проверить оплату", f"check:{order.id}", "positive")]])
    elif order.status == "canceled":
        text += "\n\nЭтот счёт отменён. Можно оформить новую покупку из меню."
    else:
        rows.append([kb.button(f"💳 Картой / СБП · {order.amount} ₽", f"buy:{order.id}", "positive")])
    rows.append([kb.button("🔮 Главное меню", "menu", "secondary")])
    await reply.send(text, kb.keyboard(rows))


def vip_text():
    return offers.vip_offer()


async def run_order(session, account, order, reply):
    try:
        report = await readings.fulfill(session, order)
    except PurchaseRequired:
        await show_order(session, account, order, reply)
        return
    except AIUnavailable:
        await reply.send("Аиша пока не смогла подготовить полный ответ. Ваш доступ сохранён. Попробуйте ещё раз чуть позже — новая оплата не нужна.",
            kb.keyboard([[kb.button("🔄 Повторить", f"run:{order.id}", "positive")], [kb.button("💜 Техподдержка", "support", "secondary")]]))
        return
    # Do not overwrite a different draft chosen while a payment was pending.
    if account.data.get("order_id") == order.id:
        state(account, "menu")
    await show_result(reply, report)


async def history(session, user, reply, page=0):
    page = max(0, page)
    reports = list((await session.scalars(select(UserReport).where(UserReport.user_id == user.id)
        .order_by(UserReport.id.desc()).offset(page*5).limit(6))).all())
    if not reports:
        await reply.send("📚 Здесь будут ваши готовые разборы. Их можно перечитывать целиком без повторной оплаты.", kb.back())
        return
    lines, rows = [], []
    for report in reports[:5]:
        lines.append(f"• {report.title}")
        rows.append([kb.button(report.title[:40], f"report:{report.id}", "secondary")])
    nav = []
    if page:
        nav.append(kb.button("← Назад", f"history:{page-1}", "secondary"))
    if len(reports)>5:
        nav.append(kb.button("Ещё →", f"history:{page+1}", "secondary"))
    if nav:
        rows.append(nav)
    await reply.send("📚 Мои разборы\n\n"+"\n".join(lines)+"\n\nНажмите название, чтобы прочитать ответ целиком.", kb.keyboard(rows))


async def profile(session, account, user, reply):
    r = await get_redis()
    vip = await is_vip(user.id)
    ttl = await r.ttl(f"vip:{user.id}") if vip else 0
    expires = datetime.now(readings.MSK)+timedelta(seconds=max(0, ttl))
    lines = [f"👤 {user.first_name}", f"Дата рождения: {user.birth_date or 'не указана'}",
             f"Email для чеков: {account.email or 'не указан'}", f"VIP до {expires:%d.%m.%Y %H:%M} МСК" if vip else "VIP не подключён", "\nВаши разборы:"]
    quotas = await get_vip_limits_summary(user.id)
    for product in kb.ORDER:
        credit = int(await r.get(f"oneoff:{product}:{user.id}") or 0)
        lines.append(f"• {kb.SHORT_NAMES[product]}: куплено {credit}"+(f", VIP {quotas[product]['remaining']}" if vip else ""))
    rows = [[kb.button("Имя", "edit:name", "secondary"), kb.button("Дата рождения", "edit:birth", "secondary")],
            [kb.button("Email для чеков", "edit:email", "secondary"), kb.button("🧾 Покупки", "orders")],
            [kb.button("🌙 Новый контекст", "new_context", "secondary"), kb.button("🔕 Напоминания", "mute", "secondary")],
            [kb.button("Прежняя консультация", "legacy", "secondary"), kb.button("💜 Как это работает", "help", "secondary")]]
    await reply.send("\n".join(lines), kb.keyboard(rows))


async def referral_rewards(session, account):
    if not account.referrer_id:
        return
    inviter = await session.get(VKAccount, account.referrer_id)
    if not inviter:
        return
    total = await session.scalar(select(func.count()).select_from(VKAccount).join(User, User.id==VKAccount.user_id)
        .where(VKAccount.referrer_id==inviter.vk_id, User.birth_date.is_not(None)))
    from bot.handlers.referral import REFERRAL_LEVELS
    for threshold, label, rewards in REFERRAL_LEVELS:
        key = f"vk:{inviter.vk_id}:{threshold}"
        if total >= threshold and not await session.get(VKReferralReward, key):
            for product, amount in rewards:
                if product == "vip_days":
                    await activate_vip(inviter.user_id, amount, event_id=f"{key}:{product}")
                else:
                    await add_credit(inviter.user_id, product, amount, event_id=f"{key}:{product}")
            session.add(VKReferralReward(key=key, vk_id=inviter.vk_id, threshold=threshold))
    await session.commit()


async def handle(session, maker, api, event, reply):
    account, user = await account_for(session, api, event.vk_id, event.message.get("ref", ""))
    cmd = command(event.message)
    text = (event.message.get("text") or "").strip()
    if cmd == "support":
        account.manual_support = True
        try:
            await api.messages.mark_as_important_conversation(peer_id=account.vk_id, important=1, group_id=settings.vk_group_id)
        except Exception:
            pass  # Handoff still works if the inbox marker is unavailable.
        await session.execute(update(VKOutbox).where(VKOutbox.vk_id==account.vk_id, VKOutbox.status=="pending").values(status="suppressed"))
        # Exactly one handoff instruction; later client messages receive no auto-reply.
        await reply.send("💜 Техподдержка\n\nНапишите ваш вопрос здесь. Вам ответит владелец сообщества вручную в этой же переписке. Автоответы бота отключены.\n\nКогда захотите вернуться к услугам, нажмите кнопку внизу.",
            kb.keyboard([[kb.button("🔮 Вернуться к боту", "resume")]], inline=False))
        for row in session.new:
            if isinstance(row, VKOutbox):
                row.body = {**row.body, "_support_notice": True}
        return
    if cmd == "resume":
        account.manual_support = False
        await show_menu(account, reply)
        return
    if account.manual_support:
        return
    await recover_pending(session, user.id)
    if event.message.get("internal") == "paid":
        order = await session.get(VKOrder, event.message["order_id"])
        if not order or order.user_id != user.id:
            return
        if order.product == "vip":
            await reply.send("💎 Оплата получена. VIP активирован на 30 дней; при продлении прежний срок и остатки сохранены.", kb.home())
            await profile(session, account, user, reply)
        else:
            await reply.send(f"✅ Оплата получена: {PRODUCTS[order.product]['name']}. Готовлю разбор по данным вашего заказа.")
            await run_order(session, account, order, reply)
        return
    if cmd == "menu":
        await show_menu(account, reply, welcome=text.lower() in ("начать", "/start", "старт"))
    elif cmd == "catalog" or cmd.startswith("catalog:"):
        try:
            page = int(cmd.split(":", 1)[1]) if ":" in cmd else 0
        except ValueError:
            page = 0
        await show_catalog(account, reply, page)
    elif cmd == "free":
        state(account, "menu")
        await reply.send("🌙 Бесплатно каждый день\n\nГороскоп и одна «Энергия дня». Повторное открытие показывает сохранённый ответ. Новый день начинается в полночь по Москве.",
            kb.keyboard([[kb.button("🔯 Гороскоп дня", "daily:horoscope", "positive")], [kb.button("⚡ Энергия дня", "daily:daily_energy", "positive")]]))
    elif cmd.startswith("daily:") and cmd[6:] in ("horoscope", "daily_energy"):
        if not user.birth_date:
            state(account, "birth", resume=cmd)
            await reply.send("🌙 Напишите дату рождения: ДД.ММ.ГГГГ.", kb.back())
        else:
            try:
                await show_result(reply, await readings.daily_report(session, user, cmd[6:]))
            except AIUnavailable:
                await reply.send("Пока не получилось подготовить прогноз. Попробуйте позже — бесплатная возможность сохранена.", kb.back())
    elif cmd.startswith("product:") and cmd[8:] in PRODUCTS:
        product = cmd[8:]
        state(account, "menu")
        await reply.send(offer(product), kb.keyboard([[kb.button(offers.ACTION_LABELS[product], f"begin:{product}", "positive")], [kb.button("🔮 Все услуги", "catalog", "secondary")]]))
    elif cmd.startswith("begin:") and cmd[6:] in PRODUCTS:
        product = cmd[6:]
        await begin(account, user, product, reply)
        if user.birth_date and product in ("tarot_card", "full_matrix"):
            await prepare(session, account, user, event, reply)
    elif cmd == "vip":
        order = VKOrder(id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"vk-vip:{event.event_key}")), user_id=user.id,
            vk_id=account.vk_id, product="vip", amount=VIP_PLAN["price_rub"], details={})
        existing = await session.get(VKOrder, order.id)
        if existing:
            order = existing
        else:
            session.add(order)
        await session.flush()
        await show_order(session, account, order, reply)
    elif cmd.startswith(("run:", "buy:", "check:", "order:")):
        action, oid = cmd.split(":",1)
        order = await session.get(VKOrder, oid)
        if not order or order.user_id != user.id:
            await reply.send("Заказ не найден. Откройте ваши покупки в профиле.", kb.back())
        elif action == "run" and order.product != "vip":
            await run_order(session, account, order, reply)
        elif action == "buy":
            if order.status in ("paid", "fulfilled"):
                if order.product != "vip":
                    await run_order(session, account, order, reply)
                else:
                    await profile(session, account, user, reply)
            elif order.product != "vip" and await can_use_product(user.id, order.product):
                await show_order(session, account, order, reply)
            else:
                state(account, "email", order_id=oid)
                rows = [[kb.button("Использовать сохранённый email", "email:saved", "positive")]] if account.email else []
                rows.append([kb.button("🔮 Главное меню", "menu", "secondary")])
                await reply.send("💌 На какой email отправить чек?\nВведите адрес. Данные банковской карты здесь не нужны — они вводятся на странице ЮKassa."+(f"\n\nСохранён: {account.email}" if account.email else ""), kb.keyboard(rows))
        elif action == "check":
            try:
                status = await check_order(maker, order)
                await session.refresh(order)
                if status == "succeeded":
                    await reply.send("✅ Оплата подтверждена. Доступ зачислен. Готовый разбор будет здесь и в истории.", kb.home())
                    if order.report_id:
                        await show_result(reply, await session.get(UserReport, order.report_id))
                    elif order.product != "vip":
                        await run_order(session, account, order, reply)
                elif status == "canceled":
                    await reply.send("Счёт отменён. Если деньги списались, напишите в техподдержку. Иначе можно оформить новый заказ.", kb.back())
                else:
                    await show_order(session, account, order, reply)
            except Exception as exc:
                if isinstance(exc, AIUnavailable):
                    raise
                await reply.send("Пока не удалось проверить оплату. Не платите повторно, если деньги списались. Попробуйте проверку позже или напишите в техподдержку.",
                    kb.keyboard([[kb.button("✅ Проверить снова", f"check:{oid}", "positive")], [kb.button("💜 Техподдержка", "support", "secondary")]]))
        else:
            await show_order(session, account, order, reply)
    elif cmd == "history" or cmd.startswith("history:"):
        await history(session, user, reply, int(cmd.split(":")[1]) if ":" in cmd and cmd.split(":")[1].isdigit() else 0)
    elif cmd == "last":
        report = await session.scalar(select(UserReport).where(UserReport.user_id==user.id).order_by(UserReport.id.desc()).limit(1))
        await show_result(reply, report) if report else await history(session, user, reply)
    elif cmd.startswith("report:") and cmd[7:].isdigit():
        report = await get_report_by_id(session, int(cmd[7:]), user.id)
        await show_result(reply, report) if report else await reply.send("Разбор не найден.", kb.back())
    elif cmd.startswith("clarify:") and cmd[8:].isdigit():
        report = await get_report_by_id(session, int(cmd[8:]), user.id)
        meta = report.metadata_json or {} if report else {}
        if not report or report.report_type != "personal_question" or meta.get("parent_report_id"):
            await reply.send("Этот разбор не найден.", kb.back())
        elif meta.get("clarification_report_id"):
            await show_result(reply, await get_report_by_id(session, meta["clarification_report_id"], user.id))
        elif not is_open(report):
            await reply.send("24 часа для уточнения истекли. Сам разбор остаётся в истории.", kb.back())
        else:
            state(account, "clarification", report_id=report.id)
            await reply.send("💬 Напишите одно уточнение по этому ответу — от 5 до 1000 символов. Оно уже включено в стоимость.", kb.back())
    elif cmd == "profile":
        state(account, "menu")
        await profile(session, account, user, reply)
    elif cmd in ("edit:name", "edit:birth", "edit:email"):
        field = cmd[5:]
        state(account, f"edit_{field}")
        await reply.send({"name":"Как к вам обращаться? Напишите имя (до 60 символов).", "birth":"Введите новую дату рождения: ДД.ММ.ГГГГ. Уже оплаченные заказы сохранят прежние данные.", "email":"Введите новый email для чеков."}[field], kb.back())
    elif cmd == "orders":
        orders = list((await session.scalars(select(VKOrder).where(VKOrder.user_id==user.id, VKOrder.payment_id.is_not(None))
            .order_by(VKOrder.created_at.desc()).limit(5))).all())
        rows = [[kb.button(f"{o.created_at:%d.%m} · {kb.SHORT_NAMES.get(o.product,'VIP')} · {o.amount} ₽", f"order:{o.id}", "secondary")] for o in orders]
        await reply.send("🧾 Последние покупки\nОткройте заказ для проверки оплаты или получения результата." if orders else "Платежей пока нет. Ваши разовые остатки показаны в профиле.", kb.keyboard(rows) if rows else kb.back())
    elif cmd == "new_context":
        await (await get_redis()).set(f"question_context:after:{user.id}", str(time.time()))
        await reply.send("🌙 Новые личные вопросы будут рассматриваться без прежней переписки. История и покупки сохраняются.", kb.back())
    elif cmd in ("mute", "unmute"):
        from bot.services.notifications import set_muted
        await set_muted("vk", account.vk_id, cmd=="mute")
        await reply.send("Напоминания отключены. Ответы на ваши действия и подтверждения покупок продолжают работать." if cmd=="mute" else "Напоминания разрешены. Рекламные цепочки сейчас выключены.", kb.back())
    elif cmd == "help":
        await reply.send("💜 Как устроена Аиша\n\n1. Выберите услугу и заполните данные.\n2. Проверьте вопрос, цену и состав результата.\n3. Оплатите на странице ЮKassa или используйте купленный доступ/VIP.\n4. Ответ придёт сюда и сохранится в истории.\n\nОплата — разовая, автоматических списаний нет. При сбое генерации доступ сохраняется. Аккаунты ВК и Telegram раздельные: покупки между ними автоматически не переносятся.\n\nЯ — цифровой помощник, а не человек. Для общения с владельцем нажмите «Техподдержка»: бот замолчит, и вы продолжите разговор здесь.",
            kb.keyboard([[kb.button("💜 Техподдержка", "support", "secondary")],[kb.button("🔮 Меню", "menu")]]))
    elif cmd == "friends":
        total = await session.scalar(select(func.count()).select_from(VKAccount).join(User, User.id==VKAccount.user_id)
            .where(VKAccount.referrer_id==account.vk_id, User.birth_date.is_not(None)))
        await reply.send(f"👥 Друзья Аиши\n\nВаша ссылка: https://vk.me/babushkaaisha?ref=ref_{account.vk_id}\n\nПриглашено с заполненной датой рождения: {total}\n\nПодарки за новых друзей:\n1 — личный вопрос\n3 — карта дня и мини-разбор\n5 — совместимость и неделя\n10 — матрица и 2 вопроса\n20 — VIP на 3 дня\n\nКаждый уровень начисляется один раз. Друг должен впервые открыть бота по вашей ссылке и указать дату рождения.", kb.back())
    elif cmd == "learn":
        await reply.send("📖 Интересное\nНебольшие материалы о символах и самопознании.", kb.choices([
            ("numerology","✨ Нумерология"),("astrology","🌙 Астрология"),("tarot","🃏 Таро"),("compatibility","💞 Отношения")], "article"))
    elif cmd.startswith("article:"):
        from bot.handlers.content import _ARTICLES_TEXT
        article = _ARTICLES_TEXT.get(cmd[8:], {})
        value = article.get("ru", "Материал пока недоступен.") if isinstance(article, dict) else str(article)
        value = re.sub(r"[*_]", "", value)
        await reply.send(value+"\n\nЭти материалы описывают символические подходы к размышлению о себе.", kb.back())
    elif cmd == "legacy":
        from bot.vk_dialog.session_manager import get_profile, get_stage
        old = await get_profile(account.vk_id)
        stage = await get_stage(account.vk_id)
        if old.get("last_paid_result") or stage in ("paid_monthly", "accompaniment", "followup", "q29_followup", "t990_waiting_question"):
            state(account, "legacy")
            await reply.send("Открыта прежняя консультация. Напишите сообщение по ней. Для новых услуг нажмите «Услуги».", kb.home())
        else:
            await reply.send("Прежних оплаченных консультаций не найдено. Новые услуги доступны в меню.", kb.back())
    else:
        await input_step(session, account, user, api, event, reply, cmd, text)


async def input_step(session, account, user, api, event, reply, cmd, text):
    data = dict(account.data or {})
    if account.state in ("birth", "edit_birth", "partner") and not cmd:
        birth = parse_birth_date(text)
        if not birth or birth.year < 1900 or birth > readings.today():
            await reply.send("Не получилось прочитать дату. Напишите существующую дату рождения в формате ДД.ММ.ГГГГ, не в будущем.", kb.back())
            return
        if account.state == "partner":
            state(account, "inputs", **{**data, "partner_date": f"{birth:%d.%m.%Y}"})
            await reply.send("💞 Какой тип отношений разбираем?", kb.choices(readings.RELATION_NAMES.items(), "relation"))
            return
        user.birth_date = f"{birth:%d.%m.%Y}"
        await session.commit()
        await referral_rewards(session, account)
        resume = data.get("resume")
        if resume and resume.startswith("daily:"):
            try:
                await show_result(reply, await readings.daily_report(session, user, resume[6:]))
                state(account, "menu")
            except AIUnavailable:
                await reply.send("Прогноз пока недоступен. Дата сохранена, попробуйте позже в разделе «Бесплатно».", kb.back())
        elif resume in PRODUCTS:
            await begin(account, user, resume, reply)
            if resume in ("tarot_card", "full_matrix"):
                await prepare(session, account, user, event, reply)
        else:
            state(account, "menu")
            await profile(session, account, user, reply)
    elif account.state == "edit_name" and not cmd:
        if not 1 <= len(text) <= 60 or "\n" in text:
            await reply.send("Напишите имя одной строкой, до 60 символов.", kb.back())
            return
        user.first_name = text
        state(account, "menu")
        await profile(session, account, user, reply)
    elif account.state in ("email", "edit_email") and (not cmd or cmd == "email:saved"):
        email = account.email if cmd == "email:saved" else text
        if not email or len(email)>254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            await reply.send("Проверьте email — например, name@example.ru. Номер карты сюда присылать не нужно.", kb.back())
            return
        account.email = email
        if account.state == "edit_email":
            state(account, "menu")
            await profile(session, account, user, reply)
            return
        order = await session.get(VKOrder, data["order_id"])
        if not order or order.user_id != user.id:
            state(account, "menu")
            await reply.send("Заказ не найден.", kb.back())
            return
        try:
            await checkout(session, order, email)
        except Exception:
            await reply.send("Не удалось создать ссылку оплаты. Деньги не списывались этим действием. Попробуйте позже.",
                kb.keyboard([[kb.button("🔄 Повторить", f"buy:{order.id}", "positive")], [kb.button("💜 Техподдержка", "support", "secondary")]]))
            return
        state(account, "ready", order_id=order.id)
        await show_order(session, account, order, reply)
    elif account.state == "clarification" and not cmd:
        if not 5<=len(text)<=1000:
            await reply.send("Уточнение должно содержать от 5 до 1000 символов.", kb.back())
            return
        try:
            report = await clarify(session, user.id, data["report_id"], text, "ru")
            await show_result(reply, report)
            state(account, "menu")
        except ClarificationUnavailable:
            state(account, "menu")
            await reply.send("Срок уточнения истёк. Исходный ответ остаётся в истории.", kb.back())
        except AIUnavailable:
            await reply.send("Не получилось подготовить уточнение. Оно не потрачено — отправьте вопрос ещё раз позже.", kb.back())
    elif account.state == "inputs":
        product = data.get("product")
        if cmd.startswith("page:"):
            _, prefix, page = cmd.split(":")
            items = readings.SPHERE_NAMES.items() if prefix=="sphere" else [(k,v) for k,v in readings.EVENT_NAMES.items() if k not in ("medical","investment")]
            await reply.send("Выберите подходящий вариант:", kb.choices(items, prefix, int(page) if page.isdigit() else 0))
        elif product == "personal_question" and not cmd:
            if not 10<=len(text)<=2000:
                await reply.send("Напишите один вопрос и контекст: от 10 до 2000 символов.", kb.back())
                return
            account.data = {**data, "question": text}
            await prepare(session, account, user, event, reply)
        elif cmd.startswith("sphere:") and product in ("mini_reading", "weekly_report") and cmd[7:] in readings.SPHERE_NAMES:
            account.data = {**data, "sphere": cmd[7:]}
            await prepare(session, account, user, event, reply)
        elif cmd.startswith("relation:") and product == "compatibility" and cmd[9:] in readings.RELATION_NAMES and data.get("partner_date"):
            account.data = {**data, "relation": cmd[9:]}
            await prepare(session, account, user, event, reply)
        elif cmd.startswith("event:") and product == "date_selection" and cmd[6:] in readings.EVENT_NAMES and cmd[6:] not in ("medical","investment"):
            account.data = {**data, "event": cmd[6:]}
            await reply.send("На какой период подобрать пять дат?", kb.choices([("30","Ближайшие 30 дней"),("60","Ближайшие 60 дней")], "days"))
        elif cmd.startswith("days:") and product=="date_selection" and data.get("event") and cmd[5:] in ("30","60"):
            account.data = {**data, "days": int(cmd[5:])}
            await reply.send("Какие дни вам подходят?", kb.choices([("all","Любые дни"),("workdays","Будни"),("weekends","Выходные")], "weekdays"))
        elif cmd.startswith("weekdays:") and product=="date_selection" and data.get("days") and cmd[9:] in ("all","workdays","weekends"):
            account.data = {**data, "weekdays": cmd[9:]}
            await prepare(session, account, user, event, reply)
        else:
            await reply.send("Выберите вариант кнопкой выше или вернитесь в меню.", kb.back())
    elif account.state == "legacy" and not cmd:
        from bot.vk_dialog.handlers import handle_vk_message
        from bot.vk_menu.support import SupportAwareAPI
        await handle_vk_message(api=SupportAwareAPI(api), uid=account.vk_id, text=text, first_name=user.first_name or "")
    elif cmd:
        await reply.send("Эта кнопка относится к предыдущему шагу. Начните нужный раздел заново — покупки и история сохранены.", kb.back())
    else:
        await show_menu(account, reply, welcome=True)
