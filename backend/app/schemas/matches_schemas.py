from pydantic import computed_field

from app.services.scoring_services import tier as _tier
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    job_id: UUID
    title: str | None
    score: float
    url: str | None = None
    detail: dict | None = None

    @computed_field
    @property
    def tier(self) -> str:
        return _tier(self.score)
