from openai import AsyncOpenAI

from app.llm.scorer_llm import LLMError

# Skills first, requirement last: consecutive calls for one resume share the same prefix,
# so Ollama can reuse the work it already did on the skills list.
PROMPT = """CANDIDATE SKILLS:
{skills}

JOB REQUIREMENT:
{requirement}

Does the candidate meet this requirement, judging only from the skills listed above?
Answer "yes" if the skills clearly cover it, "partial" if they cover some of it, "no" if they don't.
Years of experience or degrees that are not listed count as not shown.
Answer with one word: yes, partial, or no."""

VERDICTS = {"yes": 1.0, "partial": 0.5, "no": 0.0}


class FitJudge:
    def __init__(self, client: AsyncOpenAI, model: str):
        self.client = client
        self.model = model

    async def __call__(self, requirement: str, skills: list[str]) -> float:
        resp = await self.client.chat.completions.create(
            model=self.model, temperature=0, max_tokens=3,
            messages=[{"role": "user", "content": PROMPT.format(skills=", ".join(skills), requirement=requirement)}],
        )
        answer = (resp.choices[0].message.content or "").strip().lower().strip(".!\"' ")
        for word, value in VERDICTS.items():
            if answer.startswith(word):
                return value
        raise LLMError(f"fit judge gave no verdict: {answer!r}")
