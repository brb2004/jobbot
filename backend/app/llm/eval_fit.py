"""Eval: does the fit judge agree with known answers? Re-run after any prompt or model change."""
import asyncio
from collections import Counter

from openai import AsyncOpenAI

from app.core.config_core import get_settings
from app.llm.fit_judge_llm import FitJudge
from app.llm.scorer_llm import LLMError

# Fixed skills list (from the real resume), so results are comparable run to run.
SKILLS = ["C", "Python", "JavaScript", "SQL", "Bash", "FastAPI", "SQLAlchemy", "REST APIs", "JWT",
          "PostgreSQL", "SQLite", "React", "React Router", "Tailwind CSS", "Linux", "Docker", "Kubernetes",
          "QEMU", "Make", "GDB", "Git", "GitHub Actions", "CI", "Prometheus", "Grafana", "readelf",
          "x86-64 assembly", "selectolax", "Power BI", "Microsoft Forms"]

YES, PARTIAL, NO, SOFT = 1.0, 0.5, 0.0, None
CASES = [
    # clearly covered by the skills list
    ("Experience working with databases", YES),
    ("Proficiency in Python", YES),
    ("Experience building REST APIs", YES),
    ("Comfortable working in Linux environments", YES),
    ("Hands-on experience with Docker and Kubernetes", YES),
    # partly covered
    ("Distributed systems and microservices, designing service APIs, including HTTP/REST or gRPC", PARTIAL),
    ("Observability: logs, metrics, and tracing to diagnose production issues", PARTIAL),
    ("Backend development in Python or Go, including writing automated tests", PARTIAL),
    # not shown by a skills list
    ("An ability to thrive in a fast-paced environment", SOFT),
    ("A growth mindset and constant curiosity", SOFT),
    ("Excellent written and verbal communication skills", SOFT),
    ("Backend development in Go", NO),
    ("Operated AWS infrastructure with Terraform", NO),
    ("Proficiency in Java or Ruby", NO),
    ("5+ years in security engineering", NO),
    ("Experience with blockchain protocols and smart contracts", NO),
    ("Experience with Lakebase or Neon", NO),
    ("Experience in using AI to address production and operational challenges", NO),
    ("Incident response, on-call rotations, runbooks, and postmortem processes", NO),
    ("Strong collaboration skills across workstreams", SOFT),
]

NAME = {YES: "yes", PARTIAL: "partial", NO: "no", SOFT: "soft", "error": "error"}


async def main():
    cfg = get_settings()
    judge = FitJudge(AsyncOpenAI(base_url=cfg.LLM_API_URL, api_key=cfg.LLM_API_KEY, timeout=300), cfg.JUDGE_MODEL)
    right, confusion = 0, Counter()
    for requirement, expected in CASES:
        try:
            got = await judge(requirement, SKILLS)
        except LLMError:
            got = "error"
        confusion[(NAME[expected], NAME[got])] += 1
        if got == expected:
            right += 1
        else:
            print(f"WRONG  {requirement[:70]!r}: said {NAME[got]}, should be {NAME[expected]}")
    print(f"\naccuracy: {right}/{len(CASES)}")
    print("expected -> got:", dict(confusion))


if __name__ == "__main__":
    asyncio.run(main())
