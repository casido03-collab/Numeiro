"""AI Service — маршрутизация запросов к OpenAI."""
import json
import logging
from openai import AsyncOpenAI
from config import settings, AI_MODELS
from bot.models.user import AIRequest
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Клиент создаётся лениво — чтобы не падать при старте без ключа
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI | None:
    global _client
    if not settings.openai_api_key:
        return None
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=90.0,        # максимум 90 сек на запрос
            max_retries=1,       # одна автоматическая повторная попытка
        )
    return _client


# Примерная стоимость за токен ($)
COST_PER_TOKEN = {
    "gpt-4o-mini": {"input": 0.000000150, "output": 0.000000600},
    "gpt-4o":      {"input": 0.000002500, "output": 0.000010000},
}

# Заглушки для работы без OpenAI
_STUB_RESPONSES: dict[str, str] = {
    "free_reading": (
        "✨ Твои числа судьбы говорят о глубоком внутреннем потенциале и умении находить нестандартные решения. "
        "Энергия этого периода направлена на развитие и обновление.\n\n"
        "Сейчас хорошее время, чтобы прислушаться к своей интуиции — она не подведёт.\n\n"
        "_Это демо-ответ. Подключи OpenAI API для персонального разбора._"
    ),
    "weekly_report": (
        "📅 *Энергия недели*\n\n"
        "✨ Общая энергия: период трансформации и новых начинаний.\n"
        "🎯 Главная тема: принятие важных решений.\n"
        "🌟 Возможности: открываются новые пути.\n"
        "⚠️ Риски: поспешность может дорого стоить.\n"
        "💡 Совет: действуй обдуманно, но не откладывай.\n"
        "💫 День силы: Среда.\n"
        "🚫 Избегай: конфликтов и споров без необходимости.\n"
        "🔮 Итог: неделя принесёт ясность.\n\n"
        "_Это демо-ответ. Подключи OpenAI API для персонального прогноза._"
    ),
    "compatibility": (
        "💞 *Совместимость*\n\n"
        "💞 Общий процент: 74% — хорошая основа для отношений.\n"
        "🌊 Эмоциональная связь: сильная, интуитивная.\n"
        "🏠 Бытовая совместимость: требует договорённостей.\n"
        "⚡ Конфликтные зоны: разные темпы жизни.\n"
        "💪 Сильная сторона: взаимодополняемость.\n"
        "🌀 Главный риск: накопление обид.\n"
        "🌟 Совет: больше открытого общения.\n"
        "🔮 Итог: у этой пары есть потенциал.\n\n"
        "_Это демо-ответ. Подключи OpenAI API для точного анализа._"
    ),
    "daily_forecast": (
        "⚡ Энергия дня: спокойная, созидательная.\n"
        "💡 Совет дня: сосредоточься на деталях.\n"
        "⚠️ Внимание: не торопись с решениями.\n"
        "✅ Удачное действие: начать что-то новое.\n"
        "🔢 Число дня: 6\n"
        "✨ Аффирмация: Я нахожусь в потоке и принимаю лучшее.\n\n"
        "_Это демо-ответ. Подключи OpenAI API для персонального прогноза._"
    ),
    "personal_question": (
        "🔮 Что говорит энергетика: ситуация требует терпения.\n"
        "💫 Что важно учесть: твои внутренние сомнения — это сигнал, не препятствие.\n"
        "🌟 Совет: доверяй процессу и двигайся маленькими шагами.\n"
        "⚡ Возможный сценарий: в ближайшие недели придёт ясность.\n\n"
        "_Это демо-ответ. Подключи OpenAI API для персонального ответа._"
    ),
    "full_matrix": (
        "🌟 *Матрица судьбы*\n\n"
        "🌟 Ключевые энергии: трансформация и рост.\n"
        "💪 Сильные стороны: интуиция, лидерство, творческое мышление.\n"
        "⚡ Слабые стороны: склонность к перфекционизму.\n"
        "🔮 Кармические задачи: научиться принимать помощь.\n"
        "💰 Деньги: потенциал раскрывается через собственное дело.\n"
        "💞 Отношения: глубокие, но требуют открытости.\n"
        "🎨 Таланты: работа с людьми, творчество.\n"
        "🌙 Предназначение: вдохновлять и создавать.\n"
        "📅 Рекомендации на неделю: выдели время для себя.\n\n"
        "_Это демо-ответ. Подключи OpenAI API для полного разбора._"
    ),
    "date_selection": (
        "Выбранные даты обладают благоприятной нумерологической энергией для твоего события. "
        "Числа этих дней поддерживают начинания и усиливают намерение.\n\n"
        "_Это демо-ответ. Подключи OpenAI API для персонального обоснования._"
    ),
}


async def _log_request(
    session: AsyncSession,
    user_id: int,
    request_type: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    costs = COST_PER_TOKEN.get(model, COST_PER_TOKEN["gpt-4o-mini"])
    estimated_cost = input_tokens * costs["input"] + output_tokens * costs["output"]
    req = AIRequest(
        user_id=user_id,
        request_type=request_type,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=model,
        estimated_cost=estimated_cost,
    )
    session.add(req)
    await session.commit()


async def generate(
    session: AsyncSession,
    user_id: int,
    request_type: str,
    system_prompt: str,
    user_message: str,
    complexity: str = "medium",
    max_tokens: int = 1200,
) -> str:
    """Generate AI response. Falls back to stub if OpenAI key is missing."""
    client = _get_client()

    if client is None:
        logger.warning("OpenAI key not set — returning stub response for '%s'", request_type)
        return _STUB_RESPONSES.get(request_type, "✨ AI-ответ временно недоступен. Попробуйте позже.")

    model = AI_MODELS.get(complexity, AI_MODELS["medium"])

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=max_tokens,
            temperature=0.85,
        )
        content = response.choices[0].message.content or ""
        usage = response.usage
        await _log_request(
            session, user_id, request_type, model,
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
        )
        return content

    except Exception as e:
        logger.error("OpenAI error for user %s / type %s: %s", user_id, request_type, e)
        return _STUB_RESPONSES.get(
            request_type,
            "🌙 Что-то пошло не так при генерации ответа. Попробуй чуть позже."
        )
