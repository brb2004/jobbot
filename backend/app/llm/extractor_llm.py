import json
import re

from openai import AsyncOpenAI

from app.llm.scorer_llm import MAX_CHARS, LLMError, unique

PROMPT = """List the skills, tools, technologies, and qualifications mentioned in the text below.
Use short names of 1 to 4 words each, like "Python", "Kubernetes", "REST APIs", "5+ years experience".
Reply with a JSON array of strings only.

TEXT:
{text}"""


class LLMExtractor:
    def __init__(self, client: AsyncOpenAI, model: str):
        self.client = client
        self.model = model

    async def extract(self, text: str) -> list[str]:
        resp = await self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[{"role": "user", "content": PROMPT.format(text=text[:MAX_CHARS])}],
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