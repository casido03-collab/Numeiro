"""Validated OpenAI gateway for conversational channels."""
from bot.services.ai_service import complete

async def generate_business(system_prompt: str, user_message: str,
                            complexity: str = "simple", max_tokens: int = 1600,
                            cache_key: str | None = None) -> str:
    if cache_key:
        from bot.services.cache import get_redis
        r = await get_redis()
        cached = await r.get(f"paid_answer:{cache_key}")
        if cached:
            return cached
    # Legacy call sites had 300–900 tokens for 300–500 words in Russian.
    budget = max(max_tokens, 2400 if complexity in ("medium", "complex") else 800)
    content, _, _ = await complete(system_prompt, user_message, complexity, budget)
    if cache_key:
        await r.set(f"paid_answer:{cache_key}", content)
    return content
