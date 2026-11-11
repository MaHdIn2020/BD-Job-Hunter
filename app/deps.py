"""FastAPI dependencies, template context builder, and user-scoped query helpers."""

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.application import Application, SavedJob
from app.models.job import Job
from app.models.profile import Profile
from app.models.user import User
from app.services.security import get_csrf_token, pop_flash


class LoginRequiredRedirect(Exception):
    """Raised when an unauthenticated request accesses a protected HTML page."""


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """Return the logged-in User from session, or None if not logged in.

    If session has a user_id that does not exist in DB, clear the session.
    """
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    if not isinstance(user_id, int):
        request.session.clear()
        return None
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        request.session.clear()
        return None
    return user


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Require an authenticated User or redirect to /login (clearing stale sessions)."""
    user = get_current_user_optional(request, db)
    if user is None:
        raise LoginRequiredRedirect()
    return user


def build_template_context(
    request: Request,
    current_user: User | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build standard Jinja2 context with csrf_token, current_user, and popped session flash."""
    flash_message, flash_type = pop_flash(request)
    context: dict[str, Any] = {
        "current_user": current_user,
        "csrf_token": get_csrf_token(request),
        "flash_message": flash_message,
        "flash_type": flash_type,
    }
    context.update(extra)
    return context


def visible_jobs_query(user: User) -> Select[tuple[Job]]:
    """Return SQLAlchemy Select for jobs visible to user (public/demo/API + user's manual jobs)."""
    return select(Job).where(
        or_(
            Job.created_by_user_id.is_(None),
            Job.created_by_user_id == user.id,
        )
    )


def get_profile_for_user(
    db: Session,
    user: User,
    profile_id: int | None = None,
) -> Profile:
    """Return user's Profile (optionally matching profile_id) or raise 404 Not Found."""
    stmt = select(Profile).where(Profile.user_id == user.id)
    if profile_id is not None:
        stmt = stmt.where(Profile.id == profile_id)
    profile = db.scalar(stmt)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    return profile


def get_visible_job_or_404(db: Session, user: User, job_id: int) -> Job:
    """Return a Job by ID if visible to user (public or owned by user), else raise 404."""
    stmt = visible_jobs_query(user).where(Job.id == job_id)
    job = db.scalar(stmt)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


def get_application_for_user(db: Session, user: User, application_id: int) -> Application:
    """Return an Application owned by user or raise 404 Not Found."""
    stmt = select(Application).where(
        Application.id == application_id,
        Application.user_id == user.id,
    )
    application = db.scalar(stmt)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )
    return application


def get_saved_job_for_user(db: Session, user: User, saved_job_id: int) -> SavedJob:
    """Return a SavedJob owned by user or raise 404 Not Found."""
    stmt = select(SavedJob).where(
        SavedJob.id == saved_job_id,
        SavedJob.user_id == user.id,
    )
    saved_job = db.scalar(stmt)
    if saved_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved job not found.",
        )
    return saved_job

