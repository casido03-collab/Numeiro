"""Direct OpenAI generation. An unavailable answer is never a paid result."""
import logging
import re
from openai import AsyncOpenAI
from config import settings, AI_MODELS
from bot.models.user import AIRequest

logger = logging.getLogger(__name__)
_client: AsyncOpenAI | None = None


class AIUnavailable(RuntimeError):
    """No complete answer was obtained; do not consume the customer's purchase."""


def _get_client() -> AsyncOpenAI | None:
    global _client
    if not settings.openai_api_key:
        return None
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key,
                              base_url="https://api.openai.com/v1",
                              timeout=75.0, max_retries=1)
    return _client


# USD per million tokens, Standard processing, reviewed 2026-11-03.
MODEL_PRICES = {
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6.1-terra": (1.00, 5.00),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4o": (2.50, 10.00),
}


async def complete(system_prompt, user_message, complexity="medium", max_tokens=1600):
    client = _get_client()
    if client is None:
        raise AIUnavailable("OpenAI is not configured")
    model = AI_MODELS.get(complexity, AI_MODELS["medium"])
    params = dict(model=model, messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ], max_completion_tokens=max_tokens)
    # Sampling overrides are incompatible with reasoning on newer models.
    if model.startswith(("gpt-5", "gpt-6")):
        # Public SDK escape hatch: pinned openai 1.57 predates this named argument.
        params["extra_body"] = {"reasoning_effort": "none"}
    try:
        response = await client.chat.completions.create(**params)
        choice = response.choices[0]
        content = (choice.message.content or "").strip()
        if choice.finish_reason != "stop" or getattr(choice.message, "refusal", None) or not content:
            raise AIUnavailable("Incomplete or refused response")
        # Both messengers receive plain text; avoid visible Markdown artifacts.
        content = re.sub(r"(?m)^#{1,6}\s+", "", content)
        content = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", content)
        return content, model, response.usage
    except AIUnavailable:
        raise
    except Exception as exc:
        # SDK exception strings can contain request data. Log the type only.
        logger.warning("OpenAI request failed: %s / %s", model, type(exc).__name__)
        raise AIUnavailable("OpenAI request failed") from exc


async def generate(session, user_id, request_type, system_prompt, user_message,
                   complexity="medium", max_tokens=1600) -> str:
    content, model, usage = await complete(system_prompt, user_message, complexity, max_tokens)
    minimum_words = {"personal_question": 90, "mini_reading": 100, "full_matrix": 250,
                     "compatibility": 140, "weekly_report": 200, "date_selection": 130,
                     "tarot_card": 80, "clarification": 35}.get(request_type, 0)
    if len(content.split()) < minimum_words:
        raise AIUnavailable("Answer is too short for the purchased service")
    input_tokens = usage.prompt_tokens if usage else 0
    output_tokens = usage.completion_tokens if usage else 0
    prices = MODEL_PRICES.get(model)
    if prices is None:
        logger.warning("No cost estimate configured for model %s", model)
    session.add(AIRequest(user_id=user_id, request_type=request_type, model=model,
                          input_tokens=input_tokens, output_tokens=output_tokens,
                          estimated_cost=(input_tokens * prices[0] + output_tokens * prices[1]) / 1e6 if prices else None))
    await session.flush()
    return content
