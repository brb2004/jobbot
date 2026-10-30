import httpx
from pydantic import BaseModel, field_validator

API = "https://boards-api.greenhouse.io/v1/boards"


class BoardJob(BaseModel):
    id: int
    title: str
    absolute_url: str
    updated_at: str | None = None
    location: str | None = None

    @field_validator("location", mode="before")
    @classmethod
    def flatten_location(cls, v):
        # Greenhouse sends {"name": "Remote"}; we just want "Remote"
        return v.get("name") if isinstance(v, dict) else v


async def fetch_board(client: httpx.AsyncClient, slug: str) -> list[BoardJob] | None:
    r = await client.get(f"{API}/{slug}/jobs")
    if r.status_code == 404:
        return None                         # not on Greenhouse
    r.raise_for_status()                    # anything else unexpected → loud error
    return [BoardJob.model_validate(j) for j in r.json()["jobs"]]