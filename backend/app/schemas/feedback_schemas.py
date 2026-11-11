from typing import Literal

from pydantic import BaseModel, Field


class FeedbackIn(BaseModel):
    kind: Literal["bug", "feedback", "idea"]
    message: str = Field(min_length=5, max_length=5000)
    page: str | None = Field(default=None, max_length=300)
