import json
import re

from openai import AsyncOpenAI

PROMPT = """Rate how well this candidate fits this job, from 0.0 (no fit) to 1.0 (perfect fit).
Reply with JSON only, like {{"score": 0.42}}

CANDIDATE RESUME:
{resume}

JOB TITLE: {title}
JOB DESCRIPTION:
{description}"""

MAX_CHARS = 6000          # keep prompts short: faster on the SER8, and caps a huge-resume attack


class LLMError(Exception):
    pass


class LLMScorer:
    def __init__(self, client: AsyncOpenAI, model: str):
        self.client = client
        self.model = model

    async def score(self, resume, job) -> float:
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
        match = re.search(r"\{.*\}", text, re.S)                 # dig the JSON out of any wrapping
        try:
            value = float(json.loads(match.group(0))["score"])
        except (AttributeError, ValueError, KeyError, TypeError) as e:
            raise LLMError(f"unparseable model output: {text[:100]!r}") from e
        return min(max(value, 0.0), 1.0)