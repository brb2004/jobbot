from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def fits_bcrypt(cls, v: str) -> str:
        # bcrypt's limit is 72 BYTES; accented letters take 2, emoji 4
        if len(v.encode()) > 72:
            raise ValueError("must be at most 72 bytes (accented letters and emoji count as 2-4 each)")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=72)


class TokenOut(BaseModel):
    access_token: str | None = None      # only with ?token=1 (scripts); browsers use the cookie
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    email_verified_at: datetime | None = None


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(max_length=200)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def fits_bcrypt(cls, v: str) -> str:
        if len(v.encode()) > 72:
            raise ValueError("must be at most 72 bytes (accented letters and emoji count as 2-4 each)")
        return v


class VerifyIn(BaseModel):
    token: str = Field(max_length=200)
