import json
import re

from openai import AsyncOpenAI
from pydantic import BaseModel

PROMPT = """You are screening a candidate for a job.
List the job's key requirements (skills, tools, experience level). For each one, decide if the resume shows it.
Reply with JSON only, exactly this shape:
{{"met": ["requirement the resume shows", ...], "missing": ["requirement the resume lacks", ...]}}

RESUME:
{resume}

JOB TITLE: {title}
JOB DESCRIPTION:
{description}"""

MAX_CHARS = 6000


class LLMError(Exception):
    pass


class ScoreResult(BaseModel):
    score: float
    met: list[str]
    missing: list[str]


class LLMScorer:
    def __init__(self, client: AsyncOpenAI, model: str):
        self.client = client
        self.model = model

    async def score(self, resume, job) -> ScoreResult:
        resp = await self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[{"role": "user", "content": PROMPT.format(
                resume=(resume.raw_text or "")[:MAX_CHARS],
                title=job.title or "",
                description=(job.description or "")[:MAX_CHARS],
            )}],
        )
        text = resp.choices[0].message.content or ""
        match = re.search(r"\{.*\}", text, re.S)
        try:
            data = json.loads(match.group(0))
            met = [str(x) for x in data["met"]]
            missing = [str(x) for x in data["missing"]]
        except (AttributeError, ValueError, KeyError, TypeError) as e:
            raise LLMError(f"unparseable model output: {text[:100]!r}") from e
        total = len(met) + len(missing)
        if total == 0:
            raise LLMError("model listed no requirements")
        return ScoreResult(score=round(len(met) / total, 2), met=met, missing=missing)