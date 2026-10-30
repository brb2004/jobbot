"""Eval: how often does the judge agree with known answers? Run after any prompt or model change."""
import asyncio

from openai import AsyncOpenAI

from app.core.config_core import get_settings
from app.llm.judge_llm import LLMJudge
from app.llm.scorer_llm import LLMError

# (requirement, skill, correct answer). Keep these DIFFERENT from any examples inside the prompt.
CASES = [
    ("authentication", "JWT authentication", True),
    ("SQL databases", "PostgreSQL", True),
    ("Containers", "Docker", True),
    ("Monitoring", "Prometheus", True),
    ("Unit tests", "automated test suites", True),
    ("Frontend frameworks", "React", True),
    ("Version control", "Git", True),
    ("CI/CD", "GitHub Actions", True),
    ("security", "JWT authentication", False),
    ("Open source", "GitHub Actions", False),
    ("Failure recovery", "Kubernetes", False),
    ("Rust", "C", False),
    ("Java", "JavaScript", False),
    ("Go", "Python", False),
    ("AWS", "Kubernetes", False),
    ("Social networks", "React", False),
    ("Microservices", "Kubernetes", False),
    ("Distributed systems", "Kubernetes", False),
    ("Observability", "Prometheus", True),
    ("Cloud platforms", "AWS", True),
]


async def main():
    cfg = get_settings()
    judge = LLMJudge(AsyncOpenAI(base_url=cfg.LLM_API_URL, api_key=cfg.LLM_API_KEY, timeout=300), cfg.LLM_MODEL)
    right = 0
    for req, skill, expected in CASES:
        try:
            got = await judge(req, skill)
        except LLMError:
            got = None
        ok = got == expected
        right += ok
        if not ok:
            print(f"WRONG  {req!r} <- {skill!r}: said {got}, should be {expected}")
    print(f"\naccuracy: {right}/{len(CASES)}")


if __name__ == "__main__":
    asyncio.run(main())
