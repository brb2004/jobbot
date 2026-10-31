from openai import AsyncOpenAI

from app.llm.scorer_llm import LLMError

# Skills first, requirement last: consecutive calls for one resume share the same prefix.
PROMPT = """CANDIDATE SKILLS:
{skills}

JOB REQUIREMENT:
{requirement}

First: if this requirement is a personality trait or soft skill (communication, curiosity, teamwork,
work style, "fast-paced environment", "growth mindset"), answer "soft".
Otherwise, does the candidate meet it, judging only from the skills listed above?
Answer "yes" if the skills clearly cover it, "partial" if they cover some of it, "no" if they don't.
Years of experience or degrees that are not listed count as not shown.
Answer with one word: soft, yes, partial, or no."""

VERDICTS = {"soft": None, "yes": 1.0, "partial": 0.5, "no": 0.0}


class FitJudge:
    def __init__(self, client: AsyncOpenAI, model: str):
        self.client = client
        self.model = model

    async def __call__(self, requirement: str, skills: list[str]) -> float | None:
        """1.0 yes, 0.5 partial, 0.0 no, None = soft skill (shown, not scored)."""
        resp = await self.client.chat.completions.create(
            model=self.model, temperature=0, max_tokens=3,
            messages=[{"role": "user", "content": PROMPT.format(skills=", ".join(skills), requirement=requirement)}],
        )
        answer = (resp.choices[0].message.content or "").strip().lower().strip(".!\"' ")
        for word, value in VERDICTS.items():
            if answer.startswith(word):
                return value
        raise LLMError(f"fit judge gave no verdict: {answer!r}")
