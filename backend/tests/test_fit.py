import httpx
import pytest
from openai import AsyncOpenAI

from app.llm.fit_judge_llm import FitJudge
from app.llm.scorer_llm import LLMError
from app.services.fit_services import judge_requirements


def fit_returning(content):
    def handler(request):
        return httpx.Response(200, json={
            "id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": content}}],
        })
    client = AsyncOpenAI(api_key="t", base_url="http://llm.test/v1",
                         http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return FitJudge(client, "m")


@pytest.mark.parametrize("answer,value", [("Yes", 1.0), ("partial.", 0.5), ("No", 0.0)])
async def test_reads_verdicts(answer, value):
    assert await fit_returning(answer)("Go", ["Python"]) == value


async def test_unclear_answer_raises():
    with pytest.raises(LLMError):
        await fit_returning("maybe")("Go", ["Python"])


class FakeFit:
    def __init__(self, verdicts):
        self.verdicts, self.asked = verdicts, []

    async def __call__(self, requirement, skills):
        self.asked.append(requirement)
        return self.verdicts[requirement]


async def test_partial_counts_as_half():
    r = await judge_requirements(["Go", "Docker and K8s", "Rust"], ["Docker"],
                                 FakeFit({"Go": 1.0, "Docker and K8s": 0.5, "Rust": 0.0}))
    assert (r.met, r.partial, r.missing, r.score) == (["Go"], ["Docker and K8s"], ["Rust"], 0.3)


async def test_duplicate_requirements_judged_once():
    judge = FakeFit({"Go": 1.0})
    r = await judge_requirements(["Go", "go"], ["Go"], judge)
    assert judge.asked == ["Go"]
    assert r.score == 0.33


async def test_no_requirements_means_no_score():
    assert await judge_requirements([], ["Go"], FakeFit({})) is None


async def test_reads_soft_verdict():
    assert await fit_returning("Soft.")("Thrive in a fast-paced environment", ["Python"]) is None


async def test_soft_skills_are_shown_but_not_scored():
    r = await judge_requirements(["Go", "Thrive in fast-paced environments"], ["Go"],
                                 FakeFit({"Go": 1.0, "Thrive in fast-paced environments": None}))
    assert r.score == 0.33                                   # 1 / (1 scored + 2), soft not counted
    assert r.soft == ["Thrive in fast-paced environments"]


async def test_a_job_with_only_soft_bullets_gets_no_score():
    assert await judge_requirements(["Curiosity"], ["Go"], FakeFit({"Curiosity": None})) is None


async def test_years_or_degree_requirements_are_never_soft():
    judge = FakeFit({"5+ years in security engineering": None, "Bachelor's degree in CS": None})
    r = await judge_requirements(["5+ years in security engineering", "Bachelor's degree in CS"], ["Python"], judge)
    assert r.missing == ["5+ years in security engineering", "Bachelor's degree in CS"]
    assert r.soft == []

from app.services.fit_services import profile_text


def test_profile_text_lists_every_section_that_exists():
    text = profile_text(["Python", "Docker"], ["B.S., UT Dallas"], ["IT Support"])
    assert text == "Skills: Python, Docker\nEducation: B.S., UT Dallas\nExperience: IT Support"


def test_profile_text_skips_empty_sections():
    assert profile_text(["Python"], None, []) == "Skills: Python"


async def test_missing_a_required_item_sinks_the_job():
    req = "CS degree from a university in Mexico (required)"
    r = await judge_requirements(["Databases", req], [], FakeFit({"Databases": 1.0, req: 0.0}))
    assert r.score == 0.0
    assert r.missing == [req]


async def test_few_scored_requirements_cannot_outrank_well_evidenced_ones():
    few = await judge_requirements(["A", "B"], [], FakeFit({"A": 1.0, "B": 0.0}))
    many = await judge_requirements(list("CDEFG"), [],
                                    FakeFit({"C": 1.0, "D": 0.5, "E": 0.5, "F": 0.0, "G": 0.0}))
    assert many.score > few.score
