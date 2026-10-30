from types import SimpleNamespace as NS

import httpx
import pytest
from openai import AsyncOpenAI

from app.llm.scorer_llm import LLMError, LLMScorer


def llm_returning(content):
    def handler(request):
        return httpx.Response(200, json={
            "id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": content}}],
        })
    client = AsyncOpenAI(api_key="test", base_url="http://llm.test/v1",
                         http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return LLMScorer(client, model="m")


resume, job = NS(raw_text="python"), NS(title="Backend", description="python")


async def test_score_is_share_of_requirements_met():
    r = await llm_returning('{"met": ["Python", "Postgres", "Docker"], "missing": ["Go"]}').score(resume, job)
    assert r.score == 0.75
    assert r.met == ["Python", "Postgres", "Docker"]
    assert r.missing == ["Go"]


async def test_reads_json_inside_code_fences():
    r = await llm_returning('```json\n{"met": ["Python"], "missing": []}\n```').score(resume, job)
    assert r.score == 1.0


async def test_no_requirements_is_an_error_not_a_divide_by_zero():
    with pytest.raises(LLMError):
        await llm_returning('{"met": [], "missing": []}').score(resume, job)


async def test_raises_on_unparseable_output():
    with pytest.raises(LLMError):
        await llm_returning("Great fit!").score(resume, job)