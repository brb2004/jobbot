import httpx
import pytest
from openai import AsyncOpenAI

from app.llm.judge_llm import LLMJudge
from app.llm.scorer_llm import LLMError
from app.services.judge_services import CachedJudge


def judge_returning(content):
    def handler(request):
        return httpx.Response(200, json={
            "id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": content}}],
        })
    client = AsyncOpenAI(api_key="t", base_url="http://llm.test/v1",
                         http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return LLMJudge(client, "m")


async def test_judge_reads_yes():
    assert await judge_returning("Yes.")("Databases", "PostgreSQL") is True


async def test_judge_reads_no():
    assert await judge_returning("no")("Rust", "C") is False


async def test_judge_raises_on_unclear_answer():
    with pytest.raises(LLMError):
        await judge_returning("It depends")("Rust", "C")


class CountingJudge:
    def __init__(self, answer=True, fail=False):
        self.answer, self.fail, self.calls = answer, fail, 0

    async def __call__(self, requirement, skill):
        self.calls += 1
        if self.fail:
            raise LLMError("nonsense")
        return self.answer


async def test_each_pair_is_judged_once_even_across_spellings(session):
    inner = CountingJudge(answer=True)
    judge = CachedJudge(session, inner)

    assert await judge("Databases", "PostgreSQL") is True
    assert await judge("databases", "postgresql") is True      # same pair, different case

    assert inner.calls == 1


async def test_no_verdicts_are_cached_too(session):
    inner = CountingJudge(answer=False)
    judge = CachedJudge(session, inner)

    await judge("Rust", "C")
    await judge("Rust", "C")

    assert inner.calls == 1


async def test_failed_verdict_counts_as_no_and_is_not_cached(session):
    failing = CachedJudge(session, CountingJudge(fail=True))
    assert await failing("Go", "Python") is False

    working = CountingJudge(answer=True)
    assert await CachedJudge(session, working)("Go", "Python") is True
    assert working.calls == 1                                   # it was asked again, not read from cache
