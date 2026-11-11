"""Security utilities: bcrypt hashing, email validation, CSRF tokens, login lockout, and flash."""

import re
import secrets
import time

import bcrypt
from fastapi import HTTPException, Request, status

MIN_PASSWORD_CHARS = 8
MAX_PASSWORD_BYTES = 72
MAX_EMAIL_LENGTH = 254
LOCKOUT_MAX_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 600.0

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Module-level dummy hash so unknown-email login checks take the same time as real ones.
DUMMY_PASSWORD_HASH: str = bcrypt.hashpw(
    b"dummy-timing-equalizer-password", bcrypt.gensalt()
).decode("utf-8")

# In-memory failed login tracker keyed by (lowercased_email, client_ip).
# Note: Behind a reverse proxy, request.client.host is the proxy IP unless proxy headers are parsed.
_failed_login_attempts: dict[tuple[str, str], list[float]] = {}


def normalize_and_validate_email(email: str) -> str:
    """Lowercase, trim, and validate email format and max length (254 chars)."""
    cleaned = email.strip().lower()
    if not cleaned or len(cleaned) > MAX_EMAIL_LENGTH or not EMAIL_PATTERN.match(cleaned):
        raise ValueError("Please enter a valid email address (at most 254 characters).")
    return cleaned


def validate_password_strength(password: str) -> bytes:
    """Validate password length (>=8 chars and <=72 UTF-8 bytes) and return UTF-8 bytes."""
    if len(password) < MIN_PASSWORD_CHARS:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_CHARS} characters long.")
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must not exceed {MAX_PASSWORD_BYTES} bytes.")
    return encoded


def hash_password(password: str) -> str:
    """Hash a validated password with bcrypt."""
    password_bytes = validate_password_strength(password)
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a bcrypt hash, rejecting inputs over 72 bytes safely."""
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(encoded, password_hash.encode("utf-8"))


def verify_against_dummy_hash(password: str) -> None:
    """Run bcrypt.checkpw against a module-level dummy hash to equalize response timing."""
    encoded = password.encode("utf-8")[:MAX_PASSWORD_BYTES]
    bcrypt.checkpw(encoded, DUMMY_PASSWORD_HASH.encode("utf-8"))


def get_client_ip(request: Request) -> str:
    """Return client IP address from request.

    Note: Behind a proxy, request.client.host is the proxy IP.
    """
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _prune_attempts(now: float) -> None:
    """Remove expired login failure timestamps across all tracked keys."""
    cutoff = now - LOCKOUT_WINDOW_SECONDS
    expired_keys: list[tuple[str, str]] = []
    for key, timestamps in _failed_login_attempts.items():
        fresh = [ts for ts in timestamps if ts > cutoff]
        if fresh:
            _failed_login_attempts[key] = fresh
        else:
            expired_keys.append(key)
    for key in expired_keys:
        del _failed_login_attempts[key]


def is_login_locked_out(email: str, client_ip: str, now: float | None = None) -> bool:
    """Return True if (lowercased_email, client_ip) has >=5 failures in the last 10 minutes."""
    current_time = now if now is not None else time.monotonic()
    _prune_attempts(current_time)
    key = (email.strip().lower(), client_ip)
    return len(_failed_login_attempts.get(key, [])) >= LOCKOUT_MAX_ATTEMPTS


def record_failed_login(email: str, client_ip: str, now: float | None = None) -> None:
    """Record a failed login attempt for (lowercased_email, client_ip)."""
    current_time = now if now is not None else time.monotonic()
    _prune_attempts(current_time)
    key = (email.strip().lower(), client_ip)
    _failed_login_attempts.setdefault(key, []).append(current_time)


def clear_failed_logins_for(email: str, client_ip: str) -> None:
    """Clear failed login attempts for a specific (lowercased_email, client_ip)."""
    key = (email.strip().lower(), client_ip)
    _failed_login_attempts.pop(key, None)


def clear_all_login_attempts() -> None:
    """Clear all in-memory login lockout records (used in test fixtures)."""
    _failed_login_attempts.clear()


def get_csrf_token(request: Request) -> str:
    """Return existing CSRF token from session or generate a new one."""
    token = request.session.get("_csrf")
    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        request.session["_csrf"] = token
    return token


def rotate_session_for_user(request: Request, user_id: int) -> str:
    """Clear session to prevent session fixation, set user_id, and create a fresh CSRF token."""
    request.session.clear()
    request.session["user_id"] = user_id
    fresh_csrf = secrets.token_urlsafe(32)
    request.session["_csrf"] = fresh_csrf
    return fresh_csrf


def verify_csrf_token(request: Request, submitted_token: str | None) -> None:
    """Verify submitted CSRF token matches session token or raise 403 Forbidden."""
    session_token = request.session.get("_csrf")
    if (
        not isinstance(session_token, str)
        or not session_token
        or not isinstance(submitted_token, str)
        or not submitted_token
        or not secrets.compare_digest(session_token, submitted_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid.",
        )


def set_flash(request: Request, message: str, flash_type: str = "info") -> None:
    """Store a one-time flash banner message in the server-signed session."""
    request.session["_flash"] = {"message": message, "type": flash_type}


def pop_flash(request: Request) -> tuple[str | None, str]:
    """Pop and return (flash_message, flash_type) from the session."""
    raw = request.session.pop("_flash", None)
    if isinstance(raw, dict):
        msg = raw.get("message")
        tone = raw.get("type", "info")
        if isinstance(msg, str) and isinstance(tone, str):
            return msg, tone
    return None, "info"
