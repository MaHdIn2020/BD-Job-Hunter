"""Candidate Profile ORM model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


def utc_now() -> datetime:
    """Return current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class Profile(Base):
    """Editable candidate profile extracted from CV or entered manually."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(254), default="", nullable=False)
    education: Mapped[str] = mapped_column(Text, default="", nullable=False)
    university: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    degree: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    skills_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    languages_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    frameworks_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    projects_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    experience_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    certifications_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    cv_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cv_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="profile")

