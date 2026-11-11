"""Tests for Phase 1 frontend foundation: pages, navigation links, DEMO badges, components."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize("path", ["/", "/login", "/register"])
def test_public_frontend_pages_return_200(client: TestClient, path: str) -> None:
    """Public pages return 200 OK with HTML."""
    response = client.get(path)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.parametrize("path", ["/dashboard", "/profile", "/jobs", "/saved", "/tracker"])
def test_protected_frontend_pages_return_200_when_authenticated(
    auth_client: TestClient, path: str
) -> None:
    """Protected workspace pages return 200 OK when authenticated."""
    response = auth_client.get(path)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_landing_and_dashboard_contain_navigation_links(client: TestClient) -> None:
    """Landing page and dashboard include links to core routes and mobile menu markup."""
    from tests.conftest import extract_csrf_token

    landing_html = client.get("/").text
    for link in (
        'href="/"',
        'href="/dashboard"',
        'href="/jobs"',
        'href="/profile"',
        'href="/saved"',
        'href="/tracker"',
        'href="/login"',
        'href="/register"',
    ):
        assert link in landing_html
    assert 'id="mobile-menu-btn"' in landing_html
    assert 'id="mobile-menu"' in landing_html

    csrf = extract_csrf_token(client.get("/register").text)
    client.post(
        "/register",
        data={
            "full_name": "Nav Tester",
            "email": "nav@example.com",
            "password": "ValidPassword123!",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    dashboard_html = client.get("/dashboard").text
    for link in (
        'href="/"',
        'href="/dashboard"',
        'href="/jobs"',
        'href="/profile"',
        'href="/saved"',
        'href="/tracker"',
    ):
        assert link in dashboard_html
    assert 'action="/logout"' in dashboard_html
    assert 'id="mobile-menu-btn"' in dashboard_html
    assert 'id="mobile-menu"' in dashboard_html


def test_sample_jobs_clearly_badged_demo_and_safety_notice_shown(
    auth_client: TestClient,
) -> None:
    """Sample job cards on landing and dashboard carry visible DEMO badges and safety reminder."""
    for route in ("/", "/dashboard"):
        html = auth_client.get(route).text
        assert "DEMO" in html
        assert "Junior Backend Developer (Python/Django)" in html
        assert "Review before sending. BD Job Hunter never sends emails for you." in html


def test_dashboard_includes_loading_empty_state_and_session_flash(
    client: TestClient,
) -> None:
    """Dashboard renders session flash once after registration, plus loading and empty state."""
    from tests.conftest import extract_csrf_token

    reg_html = client.get("/register").text
    csrf = extract_csrf_token(reg_html)
    response = client.post(
        "/register",
        data={
            "full_name": "Arif Rahman",
            "email": "arif@example.com",
            "password": "StrongPassword123",
            "csrf_token": csrf,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.text

    assert 'id="global-loading"' in html
    assert "data-empty-state" in html
    assert "data-flash-banner" in html
    assert "Welcome to BD Job Hunter! Your account is ready." in html

    # Flash is popped from session on the first render
    second_html = client.get("/dashboard").text
    assert "Welcome to BD Job Hunter! Your account is ready." not in second_html


def test_dashboard_ignores_flash_query_param(auth_client: TestClient) -> None:
    """Query param ?flash=Hello cannot spoof or inject a banner message on /dashboard."""
    response = auth_client.get("/dashboard?flash=Hello")
    assert response.status_code == 200
    assert "Hello" not in response.text
