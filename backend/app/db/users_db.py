import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    preferences: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    links: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    tokens_valid_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    digest_opt_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Resume(Base):
    __tablename__ = "resumes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE", name="fk_resumes_user_id"), index=True
    )
    name: Mapped[str | None] = mapped_column(String(40))
    title_prefs: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    filename: Mapped[str | None] = mapped_column(String(255))
    raw_text: Mapped[str | None] = mapped_column(Text)
    years_detected: Mapped[int | None]
    skills: Mapped[list | None] = mapped_column(JSONB(none_as_null=True))
    skills_version: Mapped[str | None] = mapped_column(String(12))
    education: Mapped[list | None] = mapped_column(JSONB(none_as_null=True))
    experience: Mapped[list | None] = mapped_column(JSONB(none_as_null=True))

    user: Mapped["User"] = relationship(lazy="raise")
