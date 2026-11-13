from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # read straight from a SQLAlchemy object

    id: UUID
    title: str | None
