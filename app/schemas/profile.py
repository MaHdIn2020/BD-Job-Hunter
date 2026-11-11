"""Pydantic schemas and form parsing helpers for candidate profiles."""

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.profile import Profile
from app.services.security import normalize_and_validate_email

MAX_LIST_ITEMS = 50
MAX_ITEM_CHARS = 500
MAX_SHORT_FIELD_CHARS = 200
MAX_EDUCATION_CHARS = 2000


def _clean_string_list(values: list[Any]) -> list[str]:
    """Trim strings, drop empties, truncate to MAX_ITEM_CHARS, and deduplicate in order."""
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in values:
        if not isinstance(raw, str):
            raw = str(raw)
        item = raw.strip()[:MAX_ITEM_CHARS]
        if not item:
            continue
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            cleaned.append(item)
        if len(cleaned) >= MAX_LIST_ITEMS:
            break
    return cleaned


class ExtractedProfile(BaseModel):
    """Structured candidate profile returned by AI extraction or manual form parsing."""

    model_config = ConfigDict(extra="ignore")

    full_name: str = Field(default="")
    email: str = Field(default="")
    education: str = Field(default="")
    university: str = Field(default="")
    degree: str = Field(default="")
    skills: list[str] = Field(default_factory=list)
    programming_languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    experience: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)

    @field_validator("full_name", "email", "university", "degree", mode="before")
    @classmethod
    def coerce_short_str(cls, value: Any) -> str:
        """Coerce None to empty string and cap short fields at MAX_SHORT_FIELD_CHARS."""
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ValueError("Expected a string value.")
        return value.strip()[:MAX_SHORT_FIELD_CHARS]

    @field_validator("education", mode="before")
    @classmethod
    def coerce_education_str(cls, value: Any) -> str:
        """Coerce None to empty string and cap education summary."""
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ValueError("Expected a string value.")
        return value.strip()[:MAX_EDUCATION_CHARS]

    @field_validator(
        "skills",
        "programming_languages",
        "frameworks",
        "projects",
        "experience",
        "certifications",
        mode="before",
    )
    @classmethod
    def coerce_list_fields(cls, value: Any) -> list[str]:
        """Ensure list fields are lists of strings, trimmed and deduplicated."""
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Expected a JSON array of strings.")
        for entry in value:
            if not isinstance(entry, str):
                raise ValueError("All list items must be strings.")
        return _clean_string_list(value)


def split_comma_or_newline(raw: str) -> list[str]:
    """Split text on commas or newlines, trim, drop empty, dedupe, and enforce limits."""
    parts = re.split(r"[,\r\n]+", raw)
    return _clean_string_list(parts)


def split_newline_only(raw: str) -> list[str]:
    """Split text on newlines ONLY (preserving commas inside items), trim, dedupe, and limit."""
    parts = re.split(r"[\r\n]+", raw)
    return _clean_string_list(parts)


def parse_profile_save_form(
    *,
    full_name: str,
    email: str,
    education: str,
    university: str,
    degree: str,
    skills: str,
    programming_languages: str,
    frameworks: str,
    projects: str,
    experience: str,
    certifications: str,
) -> ExtractedProfile:
    """Validate and parse manual profile form submission."""
    cleaned_name = full_name.strip()
    cleaned_email = email.strip()
    cleaned_university = university.strip()
    cleaned_degree = degree.strip()
    cleaned_education = education.strip()

    for label, val in (
        ("Full name", cleaned_name),
        ("Email", cleaned_email),
        ("University", cleaned_university),
        ("Degree", cleaned_degree),
    ):
        if len(val) > MAX_SHORT_FIELD_CHARS:
            raise ValueError(f"{label} must not exceed {MAX_SHORT_FIELD_CHARS} characters.")

    if len(cleaned_education) > MAX_EDUCATION_CHARS:
        raise ValueError(f"Education must not exceed {MAX_EDUCATION_CHARS} characters.")

    if cleaned_email:
        cleaned_email = normalize_and_validate_email(cleaned_email)

    return ExtractedProfile(
        full_name=cleaned_name,
        email=cleaned_email,
        education=cleaned_education,
        university=cleaned_university,
        degree=cleaned_degree,
        skills=split_comma_or_newline(skills),
        programming_languages=split_comma_or_newline(programming_languages),
        frameworks=split_comma_or_newline(frameworks),
        projects=split_newline_only(projects),
        experience=split_newline_only(experience),
        certifications=split_newline_only(certifications),
    )


def _loads_str_list(raw_json: str | None) -> list[str]:
    """Safely deserialize a JSON list of strings from a Profile column."""
    if not raw_json:
        return []
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return [str(item) for item in parsed if isinstance(item, str)]
    return []


def profile_model_to_schema(profile: Profile) -> ExtractedProfile:
    """Convert a SQLAlchemy Profile row into an ExtractedProfile schema."""
    return ExtractedProfile(
        full_name=profile.full_name or "",
        email=profile.email or "",
        education=profile.education or "",
        university=profile.university or "",
        degree=profile.degree or "",
        skills=_loads_str_list(profile.skills_json),
        programming_languages=_loads_str_list(profile.languages_json),
        frameworks=_loads_str_list(profile.frameworks_json),
        projects=_loads_str_list(profile.projects_json),
        experience=_loads_str_list(profile.experience_json),
        certifications=_loads_str_list(profile.certifications_json),
    )


def apply_schema_to_profile_model(profile: Profile, data: ExtractedProfile) -> None:
    """Write validated ExtractedProfile fields onto a SQLAlchemy Profile model."""
    profile.full_name = data.full_name
    profile.email = data.email
    profile.education = data.education
    profile.university = data.university
    profile.degree = data.degree
    profile.skills_json = json.dumps(data.skills, ensure_ascii=False)
    profile.languages_json = json.dumps(data.programming_languages, ensure_ascii=False)
    profile.frameworks_json = json.dumps(data.frameworks, ensure_ascii=False)
    profile.projects_json = json.dumps(data.projects, ensure_ascii=False)
    profile.experience_json = json.dumps(data.experience, ensure_ascii=False)
    profile.certifications_json = json.dumps(data.certifications, ensure_ascii=False)
