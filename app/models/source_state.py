"""SourceState ORM model for tracking external API fetch cooldowns."""

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SourceState(Base):
    """Tracks last fetch timestamp and status for external job sources."""

    __tablename__ = "source_states"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    last_fetch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

