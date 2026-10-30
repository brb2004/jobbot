from openai import AsyncOpenAI

from app.llm.scorer_llm import LLMError

PROMPT = """You are matching a skill from a resume to a requirement from a job posting.
Answer yes ONLY if the skill IS the requirement, or is a specific example of it.
Answer no if the skill is merely related, used alongside it, or covers only part of it.

Examples:
Requirement: Databases | Skill: PostgreSQL -> yes
Requirement: Continuous integration | Skill: GitHub Actions -> yes
Requirement: HTTP/REST | Skill: REST APIs -> yes
Requirement: Open-source contributions | Skill: Git -> no
Requirement: High availability | Skill: Docker -> no
Requirement: Linux | Skill: Bash -> no

Requirement: {requirement} | Skill: {skill} ->"""


class LLMJudge:
    def __init__(self, client: AsyncOpenAI, model: str):
        self.client = client
        self.model = model

    async def __call__(self, requirement: str, skill: str) -> bool:
        resp = await self.client.chat.completions.create(
            model=self.model, temperature=0, max_tokens=3,
            messages=[{"role": "user", "content": PROMPT.format(requirement=requirement, skill=skill)}],
        )
        answer = (resp.choices[0].message.content or "").strip().lower()
        if answer.startswith("yes"):
            return True
        if answer.startswith("no"):
            return False
        raise LLMError(f"judge gave no verdict: {answer!r}")
