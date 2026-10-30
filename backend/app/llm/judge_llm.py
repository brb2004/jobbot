from openai import AsyncOpenAI

from app.llm.scorer_llm import LLMError

PROMPT = """Requirement from a job posting: "{requirement}"
Skill from a candidate's resume: "{skill}"
Does having this skill satisfy the requirement? Answer with only the word yes or no."""


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
