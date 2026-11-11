"""Shared pytest fixtures for BD Job Hunter using in-memory SQLite (StaticPool)."""

import os
import re
from collections.abc import Generator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only-32chars"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.config import get_settings  # noqa: E402
from app.database import Base, create_db_engine, get_db, reset_db_engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.ai_service import clear_all_ai_rate_limits  # noqa: E402
from app.services.security import clear_all_login_attempts  # noqa: E402

CSRF_INPUT_RE = re.compile(r'name="csrf_token"\s+value="([^"]+)"')


def extract_csrf_token(html: str) -> str:
    """Extract hidden csrf_token value from rendered HTML form."""
    match = CSRF_INPUT_RE.search(html)
    assert match is not None, "CSRF token hidden input not found in HTML"
    return match.group(1)


@pytest.fixture
def db_engine() -> Iterator[Engine]:
    """Create a fresh in-memory SQLite engine with StaticPool per test."""
    clear_all_login_attempts()
    clear_all_ai_rate_limits()
    get_settings.cache_clear()
    reset_db_engine()

    engine = create_db_engine("sqlite:///:memory:")
    assert isinstance(engine.pool, StaticPool)
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        clear_all_login_attempts()
        clear_all_ai_rate_limits()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Provide a SQLAlchemy Session bound to the per-test in-memory engine."""
    testing_session_local = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_engine: Engine) -> Iterator[TestClient]:
    """Provide a FastAPI TestClient overriding get_db with in-memory SQLite."""
    testing_session_local = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    # Ensure Foreign Keys are enforced on every connection
    @event.listens_for(db_engine, "connect")
    def _fk_pragma(dbapi_conn: object, _rec: object) -> None:
        cursor = getattr(dbapi_conn, "cursor")()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_client(client: TestClient) -> TestClient:
    """Provide a TestClient logged in as a newly registered test user."""
    reg_page = client.get("/register")
    csrf_token = extract_csrf_token(reg_page.text)
    resp = client.post(
        "/register",
        data={
            "full_name": "Nusrat Jahan",
            "email": "nusrat@example.com",
            "password": "ValidPassword123!",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return client
