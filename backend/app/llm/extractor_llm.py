import json
import re

from openai import AsyncOpenAI

from app.llm.scorer_llm import MAX_CHARS, LLMError, unique

RESUME_PROMPT = """List the skills, tools, technologies, and qualifications this person has, based on the text below.
Use short names of 1 to 4 words each, like "Python", "Kubernetes", "REST APIs".
Do NOT include anything the text says was not used (for example "built without Scrapy" means skip Scrapy).
Reply with a JSON array of strings only. If there is nothing to list, reply [].

TEXT:
{text}"""

JOB_PROMPT = """From this job posting, list ONLY the qualifications a candidate needs:
required or preferred skills, tools, technologies, degrees, and years of experience.
Skip duties and responsibilities, the company description, locations, benefits, and personality traits.
Use short names of 1 to 4 words each, like "Go", "Kubernetes", "Bachelor's degree", "5+ years experience".
Reply with a JSON array of strings only. If there is nothing to list, reply [].

POSTING:
{text}"""


class LLMExtractor:
    def __init__(self, client: AsyncOpenAI, model: str, prompt: str = RESUME_PROMPT):
        self.client = client
        self.model = model
        self.prompt = prompt

    async def extract(self, text: str) -> list[str]:
        resp = await self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[{"role": "user", "content": self.prompt.format(text=text[:MAX_CHARS])}],
        )
        raw = resp.choices[0].message.content or ""
        match = re.search(r"\[.*\]", raw, re.S)
        try:
            items = json.loads(match.group(0))
        except (AttributeError, ValueError) as e:
            raise LLMError(f"unparseable model output: {raw[:100]!r}") from e
        if not isinstance(items, list):
            raise LLMError("expected a JSON array")
        return unique([str(i).strip() for i in items if str(i).strip()])
