"""Authentication routes: register, login, and logout."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import build_template_context, get_current_user_optional
from app.models.profile import Profile
from app.models.user import User
from app.services.security import (
    clear_failed_logins_for,
    get_client_ip,
    hash_password,
    is_login_locked_out,
    normalize_and_validate_email,
    record_failed_login,
    rotate_session_for_user,
    set_flash,
    verify_against_dummy_hash,
    verify_csrf_token,
    verify_password,
)

logger = logging.getLogger(__name__)
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

INVALID_CREDENTIALS_MSG = "Invalid email or password."


@router.get("/register", response_class=HTMLResponse)
def register_page(
    request: Request,
    current_user: User | None = Depends(get_current_user_optional),
) -> HTMLResponse:
    """Render registration form."""
    context = build_template_context(
        request,
        current_user=current_user,
        active_page="register",
        show_sidebar=False,
        error_message=None,
        form_full_name="",
        form_email="",
    )
    return templates.TemplateResponse(request=request, name="register.html", context=context)


@router.post("/register", response_model=None)
def register_submit(
    request: Request,
    full_name: str = Form(default=""),
    email: str = Form(default=""),
    password: str = Form(default=""),
    csrf_token: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> HTMLResponse | RedirectResponse:
    """Validate registration form, create User + Profile, rotate session, and redirect."""
    verify_csrf_token(request, csrf_token)

    cleaned_name = full_name.strip()
    if not cleaned_name or len(cleaned_name) > 120:
        context = build_template_context(
            request,
            current_user=current_user,
            active_page="register",
            show_sidebar=False,
            error_message="Please enter your full name (1 to 120 characters).",
            form_full_name=cleaned_name,
            form_email=email.strip(),
        )
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context=context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        normalized_email = normalize_and_validate_email(email)
        password_hash = hash_password(password)
    except ValueError as exc:
        context = build_template_context(
            request,
            current_user=current_user,
            active_page="register",
            show_sidebar=False,
            error_message=str(exc),
            form_full_name=cleaned_name,
            form_email=email.strip(),
        )
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context=context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    existing = db.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
        context = build_template_context(
            request,
            current_user=current_user,
            active_page="register",
            show_sidebar=False,
            error_message="An account with this email already exists.",
            form_full_name=cleaned_name,
            form_email=normalized_email,
        )
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context=context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = User(
        email=normalized_email,
        password_hash=password_hash,
        full_name=cleaned_name,
    )
    db.add(user)
    db.flush()

    profile = Profile(
        user_id=user.id,
        full_name=cleaned_name,
        email=normalized_email,
    )
    db.add(profile)
    db.commit()
    db.refresh(user)

    rotate_session_for_user(request, user.id)
    set_flash(request, "Welcome to BD Job Hunter! Your account is ready.", "success")
    logger.info("Registered user_id=%d", user.id)
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    current_user: User | None = Depends(get_current_user_optional),
) -> HTMLResponse:
    """Render login form."""
    context = build_template_context(
        request,
        current_user=current_user,
        active_page="login",
        show_sidebar=False,
        error_message=None,
        form_email="",
    )
    return templates.TemplateResponse(request=request, name="login.html", context=context)


@router.post("/login", response_model=None)
def login_submit(
    request: Request,
    email: str = Form(default=""),
    password: str = Form(default=""),
    csrf_token: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> HTMLResponse | RedirectResponse:
    """Authenticate user with timing-equalized bcrypt check and per-(email, IP) lockout."""
    verify_csrf_token(request, csrf_token)

    normalized_email = email.strip().lower()
    client_ip = get_client_ip(request)

    if is_login_locked_out(normalized_email, client_ip):
        verify_against_dummy_hash(password)
        context = build_template_context(
            request,
            current_user=current_user,
            active_page="login",
            show_sidebar=False,
            error_message=INVALID_CREDENTIALS_MSG,
            form_email=normalized_email,
        )
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context=context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        verify_against_dummy_hash(password)
        record_failed_login(normalized_email, client_ip)
        context = build_template_context(
            request,
            current_user=current_user,
            active_page="login",
            show_sidebar=False,
            error_message=INVALID_CREDENTIALS_MSG,
            form_email=normalized_email,
        )
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context=context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not verify_password(password, user.password_hash):
        record_failed_login(normalized_email, client_ip)
        context = build_template_context(
            request,
            current_user=current_user,
            active_page="login",
            show_sidebar=False,
            error_message=INVALID_CREDENTIALS_MSG,
            form_email=normalized_email,
        )
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context=context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    clear_failed_logins_for(normalized_email, client_ip)
    rotate_session_for_user(request, user.id)
    set_flash(request, "You have signed in.", "success")
    logger.info("Authenticated user_id=%d", user.id)
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
def logout_submit(
    request: Request,
    csrf_token: str | None = Form(default=None),
    current_user: User | None = Depends(get_current_user_optional),
) -> RedirectResponse:
    """Verify CSRF, clear session, and redirect to /login."""
    verify_csrf_token(request, csrf_token)
    if current_user is not None:
        logger.info("Logged out user_id=%d", current_user.id)
    request.session.clear()
    set_flash(request, "You have been logged out.", "info")
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

