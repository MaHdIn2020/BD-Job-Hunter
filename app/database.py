"""SQLAlchemy 2.0 database engine, session factory, and initialization."""

from collections.abc import Generator
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    """Enforce foreign key constraints (and ON DELETE CASCADE) on SQLite connections."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for the configured database URL."""
    url = database_url or get_settings().DATABASE_URL
    connect_args: dict[str, Any] = {}
    engine_kwargs: dict[str, Any] = {}

    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if ":memory:" in url or "mode=memory" in url:
            engine_kwargs["poolclass"] = StaticPool
        elif url.startswith("sqlite:///"):
            relative_path = url.removeprefix("sqlite:///")
            db_path = Path(relative_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url, connect_args=connect_args, **engine_kwargs)
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return or initialize the default SQLAlchemy engine."""
    global _engine, _session_factory
    if _engine is None:
        _engine = create_db_engine()
        _session_factory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the configured session factory."""
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    return _session_factory


def reset_db_engine() -> None:
    """Dispose and reset cached engine (used when switching settings in tests)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding one SQLAlchemy Session per request."""
    session_local = get_session_factory()
    db = session_local()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine: Engine | None = None) -> None:
    """Create all database tables registered on Base.metadata."""
    import app.models  # noqa: F401

    engine = target_engine or get_engine()
    Base.metadata.create_all(bind=engine)

