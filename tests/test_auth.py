"""Comprehensive Phase 2 tests: models, auth, sessions, CSRF, lockout, and access control."""

import re
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import (
    get_application_for_user,
    get_profile_for_user,
    get_saved_job_for_user,
    get_visible_job_or_404,
    visible_jobs_query,
)
from app.models import Application, ApplicationStatus, Job, Profile, SavedJob, User
from app.services.security import hash_password, is_login_locked_out, record_failed_login
from tests.conftest import extract_csrf_token


def _register_user(
    client: TestClient,
    full_name: str = "Tanvir Ahmed",
    email: str = "tanvir@example.com",
    password: str = "SecurePass123!",
) -> tuple[int, str]:
    """Helper to fetch /register CSRF token and submit registration."""
    get_resp = client.get("/register")
    token = extract_csrf_token(get_resp.text)
    post_resp = client.post(
        "/register",
        data={
            "full_name": full_name,
            "email": email,
            "password": password,
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    return post_resp.status_code, post_resp.text


def test_register_ok_lowercases_email_and_hashes_password(
    client: TestClient, db_session: Session
) -> None:
    """Registering a valid user lowercases email, stores bcrypt hash, and creates Profile."""
    status_code, _ = _register_user(
        client,
        full_name="Sadman Sakib",
        email="  SadMan.Sakib@Example.COM ",
        password="MyStrongPassword99",
    )
    assert status_code == 303

    user = db_session.scalar(select(User).where(User.email == "sadman.sakib@example.com"))
    assert user is not None
    assert user.full_name == "Sadman Sakib"
    assert user.password_hash != "MyStrongPassword99"
    assert user.password_hash.startswith("$2b$")

    profile = db_session.scalar(select(Profile).where(Profile.user_id == user.id))
    assert profile is not None
    assert profile.email == "sadman.sakib@example.com"


def test_register_duplicate_email_rejected(client: TestClient) -> None:
    """Registering twice with the same email (case-insensitive) fails on the second attempt."""
    code1, _ = _register_user(client, email="dup@example.com")
    assert code1 == 303

    code2, html2 = _register_user(client, email="DUP@Example.com")
    assert code2 == 400
    assert "An account with this email already exists." in html2


def test_register_short_and_over_72_byte_passwords_rejected(client: TestClient) -> None:
    """Passwords shorter than 8 chars or exceeding 72 UTF-8 bytes are rejected."""
    code_short, html_short = _register_user(client, email="short@example.com", password="short")
    assert code_short == 400
    assert "at least 8 characters" in html_short

    # 73 ASCII bytes -> over 72 bytes
    code_long, html_long = _register_user(client, email="long@example.com", password="a" * 73)
    assert code_long == 400
    assert "must not exceed 72 bytes" in html_long

    # Multi-byte UTF-8 characters (Bangla) exceeding 72 bytes despite <72 characters
    bangla_25_chars = "বাংলা" * 6  # 30 chars * 3 bytes = 90 UTF-8 bytes
    code_utf8, html_utf8 = _register_user(
        client, email="utf8@example.com", password=bangla_25_chars
    )
    assert code_utf8 == 400
    assert "must not exceed 72 bytes" in html_utf8


def test_register_invalid_or_overlong_email_rejected(client: TestClient) -> None:
    """Simple regex + max 254 character check rejects malformed or overlong emails."""
    code_bad, html_bad = _register_user(client, email="not-an-email", password="ValidPassword123")
    assert code_bad == 400
    assert "valid email address" in html_bad

    long_email = ("a" * 245) + "@example.com"  # 257 chars > 254
    code_long, html_long = _register_user(client, email=long_email, password="ValidPassword123")
    assert code_long == 400
    assert "valid email address" in html_long


def test_login_wrong_email_and_wrong_password_return_identical_error(client: TestClient) -> None:
    """Unknown email and wrong password return the exact same error message."""
    _register_user(client, email="real@example.com", password="CorrectPassword123")

    login_get = client.get("/login")
    csrf = extract_csrf_token(login_get.text)

    wrong_pw_resp = client.post(
        "/login",
        data={"email": "real@example.com", "password": "WrongPassword999", "csrf_token": csrf},
    )
    assert wrong_pw_resp.status_code == 400
    assert "Invalid email or password." in wrong_pw_resp.text

    unknown_email_resp = client.post(
        "/login",
        data={
            "email": "ghost@example.com",
            "password": "WrongPassword999",
            "csrf_token": extract_csrf_token(wrong_pw_resp.text),
        },
    )
    assert unknown_email_resp.status_code == 400
    assert "Invalid email or password." in unknown_email_resp.text


def test_session_and_csrf_rotated_after_login_and_old_csrf_invalid(client: TestClient) -> None:
    """Login clears session, rotates session cookie and CSRF token, invalidating old CSRF token."""
    _register_user(client, email="rotate@example.com", password="RotatePassword123")

    # Log out first
    dash_html = client.get("/dashboard").text
    logout_csrf = extract_csrf_token(dash_html)
    client.post("/logout", data={"csrf_token": logout_csrf}, follow_redirects=False)

    # Get pre-login CSRF token and session cookie
    login_page = client.get("/login")
    pre_login_csrf = extract_csrf_token(login_page.text)
    pre_login_cookie = client.cookies.get("bd_job_hunter_session")

    login_resp = client.post(
        "/login",
        data={
            "email": "rotate@example.com",
            "password": "RotatePassword123",
            "csrf_token": pre_login_csrf,
        },
        follow_redirects=False,
    )
    assert login_resp.status_code == 303
    post_login_cookie = client.cookies.get("bd_job_hunter_session")
    assert post_login_cookie != pre_login_cookie

    post_login_html = client.get("/dashboard").text
    post_login_csrf = extract_csrf_token(post_login_html)
    assert post_login_csrf != pre_login_csrf

    # Attempting to use the old pre-login CSRF token on /logout must fail with 403
    bad_logout = client.post("/logout", data={"csrf_token": pre_login_csrf})
    assert bad_logout.status_code == 403


def test_login_lockout_per_email_and_ip_and_counts_unknown_emails(client: TestClient) -> None:
    """5 failed logins in 10 minutes lock out (email, IP), including unknown emails."""
    _register_user(client, email="locked@example.com", password="CorrectPassword123")

    login_html = client.get("/login").text
    csrf = extract_csrf_token(login_html)

    # 5 failed attempts for registered email
    for _ in range(5):
        resp = client.post(
            "/login",
            data={"email": "locked@example.com", "password": "BadPassword123", "csrf_token": csrf},
        )
        assert resp.status_code == 400
        assert "Invalid email or password." in resp.text

    # 6th attempt with CORRECT password from same IP is still rejected with same message
    sixth_resp = client.post(
        "/login",
        data={"email": "locked@example.com", "password": "CorrectPassword123", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert sixth_resp.status_code == 400
    assert "Invalid email or password." in sixth_resp.text

    # Different IP for the same email is NOT locked out
    assert is_login_locked_out("locked@example.com", "testclient") is True
    assert is_login_locked_out("locked@example.com", "203.0.113.50") is False

    # Unknown email also counts toward lockout after 5 attempts
    for _ in range(5):
        record_failed_login("nobody@example.com", "198.51.100.7", now=1000.0)
    assert is_login_locked_out("nobody@example.com", "198.51.100.7", now=1200.0) is True
    # Expired after 10 minutes (600s) -> pruned on check
    assert is_login_locked_out("nobody@example.com", "198.51.100.7", now=1601.0) is False


@pytest.mark.parametrize("path", ["/dashboard", "/profile", "/jobs", "/saved", "/tracker"])
def test_protected_pages_redirect_to_login_when_unauthenticated(
    client: TestClient, path: str
) -> None:
    """Unauthenticated requests to protected pages redirect (303) to /login."""
    resp = client.get(path, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_deleted_user_session_clears_and_redirects_to_login(
    auth_client: TestClient, db_session: Session
) -> None:
    """If session holds a user_id whose User row was deleted, clear session and redirect."""
    user = db_session.scalar(select(User).where(User.email == "nusrat@example.com"))
    assert user is not None
    db_session.delete(user)
    db_session.commit()

    resp = auth_client.get("/dashboard", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_logout_clears_session(auth_client: TestClient) -> None:
    """POST /logout clears session so subsequent /dashboard request redirects to /login."""
    dash_html = auth_client.get("/dashboard").text
    csrf = extract_csrf_token(dash_html)

    logout_resp = auth_client.post("/logout", data={"csrf_token": csrf}, follow_redirects=False)
    assert logout_resp.status_code == 303
    assert logout_resp.headers["location"] == "/login"

    after_resp = auth_client.get("/dashboard", follow_redirects=False)
    assert after_resp.status_code == 303
    assert after_resp.headers["location"] == "/login"


@pytest.mark.parametrize("endpoint", ["/register", "/login", "/logout"])
def test_post_without_csrf_returns_403(client: TestClient, endpoint: str) -> None:
    """Every POST endpoint returns 403 Forbidden when CSRF token is missing or invalid."""
    resp_missing = client.post(endpoint, data={"email": "a@example.com"})
    assert resp_missing.status_code == 403

    client.get("/login")
    resp_invalid = client.post(
        endpoint,
        data={"email": "a@example.com", "csrf_token": "tampered-token"},
    )
    assert resp_invalid.status_code == 403


def test_every_post_form_in_templates_contains_csrf_token() -> None:
    """Scan all HTML templates to verify every <form method="post"> includes csrf_token."""
    templates_dir = Path(__file__).resolve().parent.parent / "app" / "templates"
    post_form_pattern = re.compile(
        r'<form\b[^>]*method=["\']post["\'][^>]*>(.*?)</form>',
        re.IGNORECASE | re.DOTALL,
    )

    found_forms = 0
    for template_path in templates_dir.rglob("*.html"):
        content = template_path.read_text(encoding="utf-8")
        for match in post_form_pattern.finditer(content):
            found_forms += 1
            form_body = match.group(1)
            assert 'name="csrf_token"' in form_body, (
                f"POST form in {template_path.name} is missing csrf_token hidden input"
            )
    assert found_forms >= 3


def test_user_a_cannot_access_user_b_resources_and_visible_jobs_query(
    db_session: Session,
) -> None:
    """Scoped helpers return 404 for another user's records; visible_jobs_query filters properly."""
    user_a = User(
        email="usera@example.com",
        password_hash=hash_password("PasswordA123"),
        full_name="User A",
    )
    user_b = User(
        email="userb@example.com",
        password_hash=hash_password("PasswordB123"),
        full_name="User B",
    )
    db_session.add_all([user_a, user_b])
    db_session.flush()

    profile_a = Profile(user_id=user_a.id, full_name="User A", email=user_a.email)
    profile_b = Profile(user_id=user_b.id, full_name="User B", email=user_b.email)

    demo_job = Job(
        title="Demo Role",
        company="Demo Corp",
        source_name="demo",
        is_demo=True,
        created_by_user_id=None,
    )
    job_a = Job(
        title="User A Manual Job",
        company="Company A",
        source_name="manual",
        is_demo=False,
        created_by_user_id=user_a.id,
    )
    job_b = Job(
        title="User B Manual Job",
        company="Company B",
        source_name="manual",
        is_demo=False,
        created_by_user_id=user_b.id,
    )
    db_session.add_all([profile_a, profile_b, demo_job, job_a, job_b])
    db_session.flush()

    saved_b = SavedJob(user_id=user_b.id, job_id=demo_job.id)
    app_b = Application(
        user_id=user_b.id,
        job_id=demo_job.id,
        status=ApplicationStatus.OFFER_RECEIVED,
    )
    db_session.add_all([saved_b, app_b])
    db_session.commit()

    # Verify ApplicationStatus stores the string value "Offer Received"
    assert app_b.status == ApplicationStatus.OFFER_RECEIVED
    assert app_b.status.value == "Offer Received"

    # visible_jobs_query for User A returns demo_job and job_a, but NEVER job_b
    visible_for_a = list(db_session.scalars(visible_jobs_query(user_a)))
    visible_ids_a = {job.id for job in visible_for_a}
    assert visible_ids_a == {demo_job.id, job_a.id}

    # User A can access own profile, demo_job, and job_a
    assert get_profile_for_user(db_session, user_a, profile_a.id).id == profile_a.id
    assert get_visible_job_or_404(db_session, user_a, demo_job.id).id == demo_job.id
    assert get_visible_job_or_404(db_session, user_a, job_a.id).id == job_a.id

    # User A requesting User B's profile, manual job, application, or saved job -> 404
    with pytest.raises(HTTPException) as exc_profile:
        get_profile_for_user(db_session, user_a, profile_b.id)
    assert exc_profile.value.status_code == 404

    with pytest.raises(HTTPException) as exc_job:
        get_visible_job_or_404(db_session, user_a, job_b.id)
    assert exc_job.value.status_code == 404

    with pytest.raises(HTTPException) as exc_app:
        get_application_for_user(db_session, user_a, app_b.id)
    assert exc_app.value.status_code == 404

    with pytest.raises(HTTPException) as exc_saved:
        get_saved_job_for_user(db_session, user_a, saved_b.id)
    assert exc_saved.value.status_code == 404

    # Deleting user_b cascades to profile_b, job_b, saved_b, app_b
    profile_b_id = profile_b.id
    job_b_id = job_b.id
    saved_b_id = saved_b.id
    app_b_id = app_b.id

    db_session.delete(user_b)
    db_session.commit()
    db_session.expire_all()
    assert db_session.scalar(select(Profile).where(Profile.id == profile_b_id)) is None
    assert db_session.scalar(select(Job).where(Job.id == job_b_id)) is None
    assert db_session.scalar(select(SavedJob).where(SavedJob.id == saved_b_id)) is None
    assert db_session.scalar(select(Application).where(Application.id == app_b_id)) is None
