"""Frontend routes for landing page, dashboard, and navigation shells."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

SAMPLE_DEMO_JOBS: list[dict[str, Any]] = [
    {
        "title": "Junior Backend Developer (Python/Django)",
        "company": "Dhaka FinTech Labs (Demo)",
        "location": "Dhaka, Bangladesh (Hybrid)",
        "employment_type": "Full-time",
        "match_label": "50% Skill Match",
        "required_skills": ["Python", "Django", "PostgreSQL", "REST API"],
        "deadline": "2026-12-15",
        "summary": "Build internal APIs and payment reconciliation services with Django.",
        "is_demo": True,
    },
    {
        "title": "Frontend React Intern",
        "company": "Chattogram Cloud Studio (Demo)",
        "location": "Remote (Bangladesh)",
        "employment_type": "Internship",
        "match_label": "75% Skill Match",
        "required_skills": ["JavaScript", "React", "Git", "Tailwind CSS"],
        "deadline": "2026-12-01",
        "summary": "Assist the UI team with responsive dashboards for SME merchants.",
        "is_demo": True,
    },
    {
        "title": "Graduate Software Engineer",
        "company": "Sylhet Data Systems (Demo)",
        "location": "Sylhet, Bangladesh",
        "employment_type": "Full-time",
        "match_label": "67% Skill Match",
        "required_skills": ["Python", "MongoDB", "Git"],
        "deadline": "2026-12-20",
        "summary": "Entry-level role for fresh CS graduates working on data pipelines.",
        "is_demo": True,
    },
]


@router.get("/", response_class=HTMLResponse)
def landing_page(request: Request) -> HTMLResponse:
    """Render the public landing page."""
    return templates.TemplateResponse(
        request=request,
        name="landing.html",
        context={
            "active_page": "landing",
            "show_sidebar": False,
            "sample_jobs": SAMPLE_DEMO_JOBS,
        },
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request) -> HTMLResponse:
    """Render the candidate dashboard shell."""
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "active_page": "dashboard",
            "show_sidebar": True,
            "sample_jobs": SAMPLE_DEMO_JOBS,
            "flash_message": "Preview mode: sample DEMO listings shown below.",
            "flash_type": "info",
        },
    )


@router.get("/login", response_class=HTMLResponse)
def login_shell(request: Request) -> HTMLResponse:
    """Render placeholder login shell (implemented in Phase 2)."""
    return templates.TemplateResponse(
        request=request,
        name="shell_page.html",
        context={
            "active_page": "login",
            "show_sidebar": False,
            "section_badge": "Authentication",
            "page_title": "Log in to BD Job Hunter",
            "page_description": "Sign in to manage your CV profile, saved jobs, and applications.",
            "empty_title": "Login form arrives in Phase 2",
            "empty_message": "Session authentication and CSRF protection are wired in Phase 2.",
            "empty_cta_url": "/dashboard",
            "empty_cta_label": "Back to Dashboard",
        },
    )


@router.get("/register", response_class=HTMLResponse)
def register_shell(request: Request) -> HTMLResponse:
    """Render placeholder registration shell (implemented in Phase 2)."""
    return templates.TemplateResponse(
        request=request,
        name="shell_page.html",
        context={
            "active_page": "register",
            "show_sidebar": False,
            "section_badge": "Authentication",
            "page_title": "Create your account",
            "page_description": "Built for Bangladeshi students and fresh graduates.",
            "empty_title": "Registration arrives in Phase 2",
            "empty_message": "Create an account to upload your CV and track job applications.",
            "empty_cta_url": "/dashboard",
            "empty_cta_label": "Preview Dashboard",
        },
    )


@router.get("/profile", response_class=HTMLResponse)
def profile_shell(request: Request) -> HTMLResponse:
    """Render placeholder CV & Profile shell (implemented in Phase 3)."""
    return templates.TemplateResponse(
        request=request,
        name="shell_page.html",
        context={
            "active_page": "profile",
            "show_sidebar": True,
            "section_badge": "CV & Profile",
            "page_title": "Candidate Profile & CV Upload",
            "page_description": "Upload a PDF or DOCX CV and edit your extracted skills.",
            "empty_title": "No CV uploaded yet",
            "empty_message": "Upload a PDF or DOCX CV to extract your editable candidate profile.",
            "empty_cta_url": "/dashboard",
            "empty_cta_label": "Return to Dashboard",
        },
    )


@router.get("/jobs", response_class=HTMLResponse)
def jobs_shell(request: Request) -> HTMLResponse:
    """Render placeholder Job Discovery shell (implemented in Phase 4)."""
    return templates.TemplateResponse(
        request=request,
        name="shell_page.html",
        context={
            "active_page": "jobs",
            "show_sidebar": True,
            "section_badge": "Job Discovery",
            "page_title": "Discover Local & Remote Jobs",
            "page_description": "Add manual BD job posts or browse attributed remote feeds.",
            "empty_title": "Job discovery feed",
            "empty_message": "Preview sample DEMO cards on the dashboard or add manual jobs.",
            "empty_cta_url": "/dashboard",
            "empty_cta_label": "View Sample DEMO Jobs",
        },
    )


@router.get("/saved", response_class=HTMLResponse)
def saved_jobs_shell(request: Request) -> HTMLResponse:
    """Render placeholder Saved Jobs shell (implemented in Phase 7)."""
    return templates.TemplateResponse(
        request=request,
        name="shell_page.html",
        context={
            "active_page": "saved",
            "show_sidebar": True,
            "section_badge": "Saved Jobs",
            "page_title": "Saved Opportunities",
            "page_description": "Bookmark roles you want to review and apply to later.",
            "empty_title": "No saved jobs yet",
            "empty_message": "Bookmark jobs from Discovery to compare match scores and deadlines.",
            "empty_cta_url": "/jobs",
            "empty_cta_label": "Explore Jobs",
        },
    )


@router.get("/tracker", response_class=HTMLResponse)
def tracker_shell(request: Request) -> HTMLResponse:
    """Render placeholder Application Tracker shell (implemented in Phase 7)."""
    return templates.TemplateResponse(
        request=request,
        name="shell_page.html",
        context={
            "active_page": "tracker",
            "show_sidebar": True,
            "section_badge": "Application Tracker",
            "page_title": "Application Status Tracker",
            "page_description": "Track every application from Interested to Offer Received.",
            "empty_title": "No applications tracked yet",
            "empty_message": "Draft a cover email or mark a job as Applied to track progress.",
            "empty_cta_url": "/jobs",
            "empty_cta_label": "Browse Jobs",
        },
    )
