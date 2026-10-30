import asyncio
import sys

from openai import AsyncOpenAI

from app.core.config_core import get_settings
from app.core.db_core import SessionLocal, engine
from app.llm.scorer_llm import LLMScorer
from app.services.scoring_services import score_new


async def main(k: int) -> None:
    cfg = get_settings()
    client = AsyncOpenAI(base_url=cfg.LLM_API_URL, api_key=cfg.LLM_API_KEY, timeout=300)
    async with SessionLocal() as s:
        n = await score_new(s, LLMScorer(client, cfg.LLM_MODEL), k=k)
    await engine.dispose()
    print(f"scored {n} pairs")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 20))