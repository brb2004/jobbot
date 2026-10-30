import json
import re

from openai import AsyncOpenAI
from pydantic import BaseModel

PROMPT = """You are screening a candidate for a job.
List the job's key requirements (skills, tools, experience level). For each one, decide if the resume shows it.
For every requirement you mark as met, copy a short EXACT quote from the resume that proves it.
Reply with JSON only, exactly this shape:
{{"met": [{{"requirement": "...", "evidence": "exact words copied from the resume"}}],
  "missing": ["requirement the resume lacks", ...]}}

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
    evidence: dict[str, str] = {}

def normalize(text: str) -> str:
    """Lowercase, punctuation -> spaces, collapse whitespace, so quotes match despite formatting."""
    return " ".join(re.sub(r"[^a-z0-9+#]+", " ", text.lower()).split())

def unique(items: list[str]) -> list[str]:
    """Drop repeats that differ only in case/punctuation, keeping the first spelling."""
    seen, out = set(), []
    for item in items:
        key = normalize(item)
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out

def verify(met: list[dict], missing: list[str], resume_text: str) -> tuple[list[str], list[str]]:
    """Keep a 'met' only if its evidence really appears in the resume. Everything else is missing."""
    resume = f" {normalize(resume_text)} "
    verified, unproven = [], list(missing)
    for item in met:
        requirement = str(item.get("requirement", "")).strip()
        evidence = normalize(str(item.get("evidence", "")))
        if not requirement:
            continue
        if evidence and f" {evidence} " in resume:        # spaces on both sides = whole words only
            verified.append(requirement)
        else:
            unproven.append(requirement)

    missing_keys = {normalize(m) for m in unproven}
    verified = [m for m in verified if normalize(m) not in missing_keys]
    return verified, unique(unproven)


class LLMScorer:
    def __init__(self, client: AsyncOpenAI, model: str):
        self.client = client
        self.model = model

    async def score(self, resume, job) -> ScoreResult:
        resume_text = (resume.raw_text or "")[:MAX_CHARS]
        resp = await self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[{"role": "user", "content": PROMPT.format(
                resume=resume_text,
                title=job.title or "",
                description=(job.description or "")[:MAX_CHARS],
            )}],
        )
        text = resp.choices[0].message.content or ""
        match = re.search(r"\{.*\}", text, re.S)
        try:
            data = json.loads(match.group(0))
            raw_met = [m for m in data["met"] if isinstance(m, dict)]
            raw_missing = [str(m) for m in data["missing"]]
        except (AttributeError, ValueError, KeyError, TypeError) as e:
            raise LLMError(f"unparseable model output: {text[:100]!r}") from e

        met, missing = verify(raw_met, raw_missing, resume_text)
        quotes = {str(i.get("requirement", "")).strip(): str(i.get("evidence", "")) for i in raw_met}
        total = len(met) + len(missing)
        if total == 0:
            raise LLMError("model listed no requirements")
        return ScoreResult(score=round(len(met) / total, 2), met=met, missing=missing,
                           evidence={req: quotes[req] for req in met})