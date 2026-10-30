import json
from types import SimpleNamespace as NS

import httpx
import pytest
from openai import AsyncOpenAI
from app.llm.extractor_llm import LLMExtractor
from app.llm.scorer_llm import LLMError, LLMScorer, verify


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


RESUME = "Built FastAPI services in Python. Ran Postgres on Kubernetes."
resume, job = NS(raw_text=RESUME), NS(title="Backend", description="python")


def met(requirement, evidence):
    return {"requirement": requirement, "evidence": evidence}


# --- verify(): the hallucination check, pure function, no LLM ---

def test_met_with_real_evidence_stays_met():
    assert verify([met("Python", "FastAPI services in Python")], [], RESUME) == (["Python"], [])


def test_met_with_invented_evidence_moves_to_missing():
    assert verify([met("Go", "5 years writing Go")], [], RESUME) == ([], ["Go"])


def test_evidence_matches_whole_words_only():
    met_items, _ = verify([met("Go", "go")], [], "Good communicator")   # "go" inside "good" doesn't count
    assert met_items == []


def test_evidence_ignores_case_and_punctuation():
    met_items, _ = verify([met("Postgres", "ran postgres on kubernetes")], [], RESUME)
    assert met_items == ["Postgres"]


def test_requirement_listed_as_both_counts_as_missing():
    assert verify([met("Python", "in Python")], ["python"], RESUME) == ([], ["python"])


# --- LLMScorer: parsing + scoring on top of verify() ---

async def test_score_uses_only_verified_matches():
    out = {"met": [met("Python", "in Python"), met("Go", "expert in Go")], "missing": ["Rust"]}
    r = await llm_returning(json.dumps(out)).score(resume, job)
    assert r.met == ["Python"]
    assert r.missing == ["Rust", "Go"]
    assert r.score == 0.33


async def test_reads_json_inside_code_fences():
    body = json.dumps({"met": [met("Python", "in Python")], "missing": []})
    r = await llm_returning(f"```json\n{body}\n```").score(resume, job)
    assert r.score == 1.0


async def test_no_requirements_is_an_error():
    with pytest.raises(LLMError):
        await llm_returning('{"met": [], "missing": []}').score(resume, job)


async def test_raises_on_unparseable_output():
    with pytest.raises(LLMError):
        await llm_returning("Great fit!").score(resume, job)
def test_duplicate_requirements_count_once():
    _, missing = verify([], ["Go", "go", "Rust"], RESUME)
    assert missing == ["Go", "Rust"]
async def test_keeps_the_quote_for_each_verified_match():
    out = {"met": [met("Python", "in Python"), met("Go", "expert in Go")], "missing": []}
    r = await llm_returning(json.dumps(out)).score(resume, job)
    assert r.evidence == {"Python": "in Python"}
def test_long_quote_does_not_count():
    summary = ("Backend and systems-focused engineer with hands-on C, Python, FastAPI, PostgreSQL, "
               "Linux, Docker, Kubernetes, CI, and observability experience.")
    met_items, _ = verify([met("5+ years in security writing Python", summary)], [], summary)
    assert met_items == []

def test_off_topic_quote_does_not_count():
    line = "Available for full-time work immediately."
    met_items, _ = verify([met("Good English communication skills", line)], [], line)
    assert met_items == []


def test_short_on_topic_quote_counts():
    met_items, _ = verify([met("Containers including Docker and Kubernetes", "Docker, Kubernetes")],
                          [], "Tools: Docker, Kubernetes")
    assert met_items == ["Containers including Docker and Kubernetes"]
def test_reworded_quote_with_real_keywords_counts():
    met_items, _ = verify([met("Containers including Docker and Kubernetes", "Docker and Kubernetes")],
                          [], "Tools: Docker, Kubernetes")
    assert met_items == ["Containers including Docker and Kubernetes"]




def extractor_returning(content):
    def handler(request):
        return httpx.Response(200, json={
            "id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": content}}],
        })
    client = AsyncOpenAI(api_key="test", base_url="http://llm.test/v1",
                         http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return LLMExtractor(client, model="m")


async def test_extracts_list_even_inside_code_fences():
    assert await extractor_returning('```json\n["Python", "Docker"]\n```').extract("x") == ["Python", "Docker"]


async def test_extractor_drops_duplicates_and_blanks():
    assert await extractor_returning('["Python", "python", " ", "Go"]').extract("x") == ["Python", "Go"]


async def test_extractor_raises_on_prose():
    with pytest.raises(LLMError):
        await extractor_returning("Python and Docker").extract("x")


async def test_extractor_raises_on_truncated_output():
    with pytest.raises(LLMError):
        await extractor_returning('["Python", "Dock').extract("x")