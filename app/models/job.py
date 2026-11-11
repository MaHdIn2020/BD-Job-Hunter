"""Job ORM model supporting manual, demo, and external API listings."""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.application import Application, SavedJob
    from app.models.user import User


def utc_now() -> datetime:
    """Return current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class Job(Base):
    """Job listing from manual entry, demo seed, or external remote job APIs."""

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source_name", "external_id", name="uq_job_source_external_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), default="Remote", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    required_skills: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    preferred_skills: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    employment_type: Mapped[str] = mapped_column(String(80), default="Full-time", nullable=False)
    experience_level: Mapped[str | None] = mapped_column(String(120), nullable=True)
    salary: Mapped[str | None] = mapped_column(String(120), nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    application_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_name: Mapped[str] = mapped_column(String(80), default="manual", nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dedupe_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    creator: Mapped["User | None"] = relationship("User", back_populates="manual_jobs")
    saved_by: Mapped[list["SavedJob"]] = relationship(
        "SavedJob",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    applications: Mapped[list["Application"]] = relationship(
        "Application",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
