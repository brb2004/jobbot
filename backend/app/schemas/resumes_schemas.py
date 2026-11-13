from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.services.preferences_services import ResumePrefs


class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str | None = None
    filename: str | None
    years_detected: int | None = None
    created_at: datetime | None = None
    title_prefs: dict | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def own(self) -> ResumePrefs:
        return ResumePrefs.model_validate(self.title_prefs or {})


class ResumeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=40)
    own: ResumePrefs | None = None
