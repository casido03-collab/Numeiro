"""Synthetic smoke test only; never imports a customer's conversation or prints keys."""
import asyncio
import json
import os
import sys
from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("BOT_TOKEN", "123456:TEST_NOT_A_REAL_BOT_TOKEN")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@127.0.0.1/test")

async def main():
    from openai import AsyncOpenAI
    from bot.services import ai_service
    from bot.prompts.prompts import PERSONAL_QUESTION_PAID_PROMPT, PAID_MINI_REPORT_PROMPT
    key = (dotenv_values(ROOT / ".env").get("OPENAI_API_KEY")
           or dotenv_values(ROOT.parent / "Numeiro" / ".env").get("OPENAI_API_KEY"))
    if not key:
        print("OpenAI key not found; no live calls made.")
        return
    client = AsyncOpenAI(api_key=key, base_url="https://api.openai.com/v1", max_retries=0, timeout=40)
    ai_service._client = client
    ai_service.settings.openai_api_key = key
    results = []
    for model in ("gpt-6-luna", "gpt-6.1-terra"):
        try:
            await client.models.retrieve(model)
            results.append({"model": model, "accessible": True})
        except Exception as exc:
            results.append({"model": model, "accessible": False, "error_type": type(exc).__name__,
                            "http_status": getattr(exc, "status_code", None)})
    if all(row["accessible"] for row in results):
        cases = [
            ("question", PERSONAL_QUESTION_PAID_PROMPT(), {"name":"Тест", "question":"Партнёр стал реже писать. Он мне изменяет?", "numbers":{"life_path":1}}),
            ("mini", PAID_MINI_REPORT_PROMPT(), {"name":"Тест", "sphere":"Работа", "numbers":{"life_path":3,"destiny":6}}),
        ]
        async def run(model, case, prompt, context):
            complexity = "complex" if model == "gpt-6.1-terra" else "medium"
            try:
                content, _, usage = await ai_service.complete(prompt, json.dumps(context,ensure_ascii=False), complexity, 2400)
                return {"model":model,"case":case,"answer":content,"input_tokens":usage.prompt_tokens,"output_tokens":usage.completion_tokens}
            except Exception as exc:
                return {"model":model,"case":case,"error_type":type(exc).__name__}
        samples = await asyncio.gather(*(run(m,c,p,x) for m in ("gpt-6-luna","gpt-6.1-terra") for c,p,x in cases))
        results += samples
    target = Path(__file__).with_name("openai-smoke-results.json")
    target.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    for result in results:
        print(json.dumps({k:v for k,v in result.items() if k != "answer"}, ensure_ascii=False))
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
