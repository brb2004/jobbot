from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ApplicationOut(BaseModel):
    job_id: UUID
    title: str | None
    company: str | None
    location: str | None
    url: str | None
    closed: bool
    applied_at: datetime
