from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints


class FeedbackIn(BaseModel):
    kind: Literal["bug", "feedback", "idea"]
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
    page: str | None = Field(default=None, max_length=300)
