"""Routes for CV upload, paste fallback, AI profile preview, manual save, and CV text deletion."""

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import build_template_context, get_current_user
from app.models.profile import Profile
from app.models.user import User
from app.schemas.profile import (
    ExtractedProfile,
    apply_schema_to_profile_model,
    parse_profile_save_form,
    profile_model_to_schema,
)
from app.services.ai_service import (
    AIServiceError,
    extract_profile_from_cv_text,
    is_ai_configured,
)
from app.services.cv_parser import (
    CVParseError,
    parse_uploaded_cv,
    validate_pasted_cv_text,
)
from app.services.security import set_flash, verify_csrf_token

logger = logging.getLogger(__name__)
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

AI_SUGGESTION_BANNER = (
    "AI suggestion - review, edit, then press Save. Nothing is saved until you do."
)


def _get_or_create_user_profile(db: Session, user: User) -> Profile:
    """Fetch the current user's Profile row, creating an empty one if missing."""
    profile = db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is None:
        profile = Profile(
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _schema_to_form_dict(data: ExtractedProfile) -> dict[str, str]:
    """Convert ExtractedProfile into string values for template form inputs/textareas."""
    return {
        "full_name": data.full_name,
        "email": data.email,
        "education": data.education,
        "university": data.university,
        "degree": data.degree,
        "skills": ", ".join(data.skills),
        "programming_languages": ", ".join(data.programming_languages),
        "frameworks": ", ".join(data.frameworks),
        "projects": "\n".join(data.projects),
        "experience": "\n".join(data.experience),
        "certifications": "\n".join(data.certifications),
    }


def _render_profile_page(
    request: Request,
    *,
    current_user: User,
    profile: Profile,
    form_data: dict[str, str] | None = None,
    error_message: str | None = None,
    ai_suggestion_banner: str | None = None,
    removed_items_count: int = 0,
    highlight_paste: bool = False,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    """Render profile.html with saved or AI-prefilled form values."""
    effective_form = form_data or _schema_to_form_dict(profile_model_to_schema(profile))
    context: dict[str, Any] = build_template_context(
        request,
        current_user=current_user,
        active_page="profile",
        show_sidebar=True,
        profile=profile,
        form_data=effective_form,
        ai_configured=is_ai_configured(),
        error_message=error_message,
        ai_suggestion_banner=ai_suggestion_banner,
        removed_items_count=removed_items_count,
        highlight_paste=highlight_paste,
    )
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context=context,
        status_code=status_code,
    )


def _run_ai_preview_for_profile(
    request: Request,
    *,
    current_user: User,
    profile: Profile,
) -> HTMLResponse:
    """Run AI extraction on profile.cv_raw_text WITHOUT writing extracted fields to DB."""
    if not profile.cv_raw_text:
        return _render_profile_page(
            request,
            current_user=current_user,
            profile=profile,
            error_message=(
                "No stored CV text found. Please upload a CV or paste your CV text first."
            ),
            highlight_paste=True,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not is_ai_configured():
        return _render_profile_page(
            request,
            current_user=current_user,
            profile=profile,
            error_message=(
                "AI is not configured. Your CV text is stored—please fill in and save "
                "your profile manually."
            ),
        )

    try:
        extracted, dropped_items = extract_profile_from_cv_text(
            profile.cv_raw_text,
            user_id=current_user.id,
        )
    except AIServiceError as exc:
        return _render_profile_page(
            request,
            current_user=current_user,
            profile=profile,
            error_message=str(exc),
        )

    if not extracted.full_name and profile.full_name:
        extracted.full_name = profile.full_name
    if not extracted.email and profile.email:
        extracted.email = profile.email

    return _render_profile_page(
        request,
        current_user=current_user,
        profile=profile,
        form_data=_schema_to_form_dict(extracted),
        ai_suggestion_banner=AI_SUGGESTION_BANNER,
        removed_items_count=len(dropped_items),
    )


@router.get("/profile", response_class=HTMLResponse)
def profile_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the current user's saved profile and CV upload/paste controls."""
    profile = _get_or_create_user_profile(db, current_user)
    return _render_profile_page(
        request,
        current_user=current_user,
        profile=profile,
    )


@router.post("/profile/upload", response_class=HTMLResponse)
def upload_cv(
    request: Request,
    cv_file: UploadFile = File(...),
    csrf_token: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Validate uploaded PDF/DOCX, store cv_filename + cv_raw_text, and prefill AI suggestion."""
    verify_csrf_token(request, csrf_token)
    profile = _get_or_create_user_profile(db, current_user)

    try:
        safe_filename, extracted_text = parse_uploaded_cv(request, cv_file)
    except CVParseError as exc:
        return _render_profile_page(
            request,
            current_user=current_user,
            profile=profile,
            error_message=str(exc),
            highlight_paste=True,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    profile.cv_filename = safe_filename
    profile.cv_raw_text = extracted_text
    db.commit()
    db.refresh(profile)
    logger.info("Stored CV text from upload for user_id=%d", current_user.id)

    return _run_ai_preview_for_profile(
        request,
        current_user=current_user,
        profile=profile,
    )


@router.post("/profile/paste", response_class=HTMLResponse)
def paste_cv(
    request: Request,
    cv_text: str = Form(default=""),
    csrf_token: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Validate pasted CV text, store on Profile, and prefill AI suggestion without saving."""
    verify_csrf_token(request, csrf_token)
    profile = _get_or_create_user_profile(db, current_user)

    try:
        validated_text = validate_pasted_cv_text(cv_text)
    except CVParseError as exc:
        return _render_profile_page(
            request,
            current_user=current_user,
            profile=profile,
            error_message=str(exc),
            highlight_paste=True,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    profile.cv_filename = "pasted_cv.txt"
    profile.cv_raw_text = validated_text
    db.commit()
    db.refresh(profile)
    logger.info("Stored pasted CV text for user_id=%d", current_user.id)

    return _run_ai_preview_for_profile(
        request,
        current_user=current_user,
        profile=profile,
    )


@router.post("/profile/extract", response_class=HTMLResponse)
def extract_cv_profile(
    request: Request,
    csrf_token: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Run AI extraction on existing cv_raw_text and prefill form without saving to DB."""
    verify_csrf_token(request, csrf_token)
    profile = _get_or_create_user_profile(db, current_user)
    return _run_ai_preview_for_profile(
        request,
        current_user=current_user,
        profile=profile,
    )


@router.post("/profile/save", response_model=None)
def save_profile(
    request: Request,
    full_name: str = Form(default=""),
    email: str = Form(default=""),
    education: str = Form(default=""),
    university: str = Form(default=""),
    degree: str = Form(default=""),
    skills: str = Form(default=""),
    programming_languages: str = Form(default=""),
    frameworks: str = Form(default=""),
    projects: str = Form(default=""),
    experience: str = Form(default=""),
    certifications: str = Form(default=""),
    csrf_token: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse | RedirectResponse:
    """Validate and save the user's edited profile fields to the database."""
    verify_csrf_token(request, csrf_token)
    profile = _get_or_create_user_profile(db, current_user)

    raw_form = {
        "full_name": full_name,
        "email": email,
        "education": education,
        "university": university,
        "degree": degree,
        "skills": skills,
        "programming_languages": programming_languages,
        "frameworks": frameworks,
        "projects": projects,
        "experience": experience,
        "certifications": certifications,
    }

    try:
        parsed = parse_profile_save_form(**raw_form)
    except ValueError as exc:
        return _render_profile_page(
            request,
            current_user=current_user,
            profile=profile,
            form_data=raw_form,
            error_message=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    apply_schema_to_profile_model(profile, parsed)
    db.commit()
    logger.info("Saved profile for user_id=%d", current_user.id)
    set_flash(request, "Your profile has been saved.", "success")
    return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/delete-cv")
def delete_stored_cv(
    request: Request,
    csrf_token: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    """Clear stored cv_filename and cv_raw_text for the current user."""
    verify_csrf_token(request, csrf_token)
    profile = _get_or_create_user_profile(db, current_user)
    profile.cv_filename = None
    profile.cv_raw_text = None
    db.commit()
    logger.info("Deleted stored CV text for user_id=%d", current_user.id)
    set_flash(request, "Stored CV text has been deleted.", "info")
    return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)
