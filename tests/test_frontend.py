"""Tests for Phase 1 frontend foundation: pages, navigation links, DEMO badges, components."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/dashboard",
        "/login",
        "/register",
        "/profile",
        "/jobs",
        "/saved",
        "/tracker",
    ],
)
def test_frontend_pages_return_200(client: TestClient, path: str) -> None:
    """Every main page and navigation shell returns 200 OK with HTML."""
    response = client.get(path)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_landing_and_dashboard_contain_navigation_links(client: TestClient) -> None:
    """Landing page and dashboard include links to all core routes and mobile menu markup."""
    expected_links = [
        'href="/"',
        'href="/dashboard"',
        'href="/jobs"',
        'href="/profile"',
        'href="/saved"',
        'href="/tracker"',
        'href="/login"',
        'href="/register"',
    ]

    for route in ("/", "/dashboard"):
        html = client.get(route).text
        for link in expected_links:
            assert link in html, f"Missing {link} on {route}"
        assert 'id="mobile-menu-btn"' in html
        assert 'id="mobile-menu"' in html


def test_sample_jobs_clearly_badged_demo_and_safety_notice_shown(client: TestClient) -> None:
    """Sample job cards on landing and dashboard carry visible DEMO badges and safety reminder."""
    for route in ("/", "/dashboard"):
        html = client.get(route).text
        assert "DEMO" in html
        assert "Junior Backend Developer (Python/Django)" in html
        assert "Review before sending. BD Job Hunter never sends emails for you." in html


def test_dashboard_includes_loading_empty_state_and_flash_components(client: TestClient) -> None:
    """Dashboard includes loading indicator, empty state, and server-side flash banner."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    html = response.text

    assert 'id="global-loading"' in html
    assert "data-empty-state" in html
    assert "data-flash-banner" in html
    assert "Preview mode: sample DEMO listings shown below." in html


def test_dashboard_ignores_flash_query_param(client: TestClient) -> None:
    """Query param ?flash=Hello cannot spoof or inject a banner message on /dashboard."""
    response = client.get("/dashboard?flash=Hello")
    assert response.status_code == 200
    assert "Hello" not in response.text
