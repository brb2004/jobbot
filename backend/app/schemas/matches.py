from uuid import UUID
from pydantic import BaseModel, ConfigDict

class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    job_id: UUID
    title: str | None
    score: float