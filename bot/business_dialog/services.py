"""AI-генерация для business dialog — изолирована от основного сервиса."""
import logging
from config import AI_MODELS, settings

logger = logging.getLogger(__name__)


async def generate_business(
    system_prompt: str,
    user_message: str,
    complexity: str = "simple",
    max_tokens: int = 200,
) -> str:
    """Генерация ответа от имени бабушки Аиши. Без логирования в основную БД."""
    from bot.services.ai_service import _get_client
    client = _get_client()

    if client is None:
        logger.warning("AI client not available — returning fallback")
        return "Душа моя 🌙\nПодожди немного, я уже смотрю твою ситуацию…"

    base_model = AI_MODELS.get(complexity, AI_MODELS["simple"])
    use_openrouter = bool(getattr(settings, "openrouter_api_key", ""))
    model = f"openai/{base_model}" if use_openrouter else base_model

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
            max_tokens=max_tokens,
            temperature=0.92,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error("Business AI error [%s]: %s", type(e).__name__, e)
        return "Душа моя 🌙\nСейчас не могу ответить. Напиши чуть позже."
