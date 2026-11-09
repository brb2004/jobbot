from uuid import UUID
from pydantic import BaseModel, ConfigDict


class ResumeOut(BaseModel):
    years_detected: int | None = None
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    filename: str | None