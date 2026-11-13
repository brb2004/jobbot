from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.services.requirements_services import years_note as _years_note
from app.services.scoring_services import tier as _tier


class MatchOut(BaseModel):
    company: str | None = None
    location: str | None = None
    model_config = ConfigDict(from_attributes=True)
    job_id: UUID
    title: str | None
    score: float
    url: str | None = None
    detail: dict | None = None
    resume: str | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def tier(self) -> str:
        return _tier(self.score)

    @computed_field
    @property
    def years_note(self) -> str | None:
        return _years_note(self.detail or {})
