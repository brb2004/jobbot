import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    preferences: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    tokens_valid_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # logout = revoke older tokens
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # None = no digests
    digest_opt_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # set = unsubscribed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str | None]
    board: Mapped[str | None] = mapped_column(String(100))
    external_id: Mapped[str | None] = mapped_column(String(64))   # the source's posting id, as text
    url: Mapped[str | None]
    location: Mapped[str | None]
    description: Mapped[str | None] = mapped_column(Text)
    content_html: Mapped[str | None] = mapped_column(Text)
    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    salary_currency: Mapped[str | None] = mapped_column(String(10))
    requirements: Mapped[list | None] = mapped_column(JSONB(none_as_null=True))
    skills: Mapped[list | None] = mapped_column(JSONB(none_as_null=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # gone from its board
    source_updated_at: Mapped[str | None] = mapped_column(String(40))  # Greenhouse updated_at, or a content hash
    skills_version: Mapped[str | None] = mapped_column(String(12))   # skills.txt hash used to tag

    __table_args__ = (
        UniqueConstraint("board", "external_id", name="uq_jobs_board_external"),
        Index("ix_jobs_open", "id", postgresql_where=closed_at.is_(None)),   # matching/digest scan open jobs only
    )


class Resume(Base):
    __tablename__ = "resumes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(                      # up to MAX_RESUMES; go with the account
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE", name="fk_resumes_user_id"), index=True)
    name: Mapped[str | None] = mapped_column(String(40))             # "Backend", "DevOps"
    title_prefs: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))  # per-resume titles/years; unset = account's
    # clock_timestamp, not now(): two uploads in one transaction still get an order (oldest = default tab)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
    filename: Mapped[str | None] = mapped_column(String(255))
    raw_text: Mapped[str | None] = mapped_column(Text)
    years_detected: Mapped[int | None]                   # from the resume text; prefs override
    skills: Mapped[list | None] = mapped_column(JSONB(none_as_null=True))
    skills_version: Mapped[str | None] = mapped_column(String(12))   # skills.txt hash used to tag
    education: Mapped[list | None] = mapped_column(JSONB(none_as_null=True))
    experience: Mapped[list | None] = mapped_column(JSONB(none_as_null=True))

    user: Mapped["User"] = relationship(lazy="raise")   # never loaded; lets the ORM insert the user row first


class MatchScore(Base):
    __tablename__ = "match_scores"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    score: Mapped[float]
    detail: Mapped[dict | None] = mapped_column(JSONB)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("resume_id", "job_id"),
        Index("ix_match_scores_job_id", "job_id"),   # ON DELETE CASCADE from jobs: no seq scan per deleted job
    )


class Application(Base):
    """A job the user applied to. status leaves room for "not interested" later."""
    __tablename__ = "applications"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="applied")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_applications_user_job"),)


class Feedback(Base):
    """A bug report or feedback, plus the queue state of its acknowledgement email (transactional outbox)."""
    __tablename__ = "feedback"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))                     # bug | feedback | idea
    message: Mapped[str] = mapped_column(Text)
    page: Mapped[str | None] = mapped_column(String(300))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="open")   # triage: open | done
    ack_status: Mapped[str] = mapped_column(String(20), default="queued")  # queued | sent | failed
    attempts: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Board(Base):
    """A job board: its key ("stripe" on Greenhouse, "ashby:ramp", "lever:spotify") and the company's name."""
    __tablename__ = "boards"
    slug: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(200))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    misses: Mapped[int] = mapped_column(default=0, server_default="0")   # consecutive 404 crawls


class DigestSent(Base):
    """One weekly digest per user per ISO week: claimed before sending, so a re-run never sends it twice."""
    __tablename__ = "digest_sent"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    week: Mapped[str] = mapped_column(String(8), primary_key=True)          # "2026-W46"
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
