import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.projects.models import PROJECT_STATUSES


def _validate_status(value: str | None) -> str | None:
    if value is not None and value not in PROJECT_STATUSES:
        raise ValueError(f"status must be one of {sorted(PROJECT_STATUSES)}")
    return value


def _normalize_name(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("name must not be blank")
    return trimmed


def _normalize_code(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    project_code: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=2000)
    status: str = "planning"

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: str) -> str:
        return _validate_status(value)

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        return _normalize_name(value)

    @field_validator("project_code")
    @classmethod
    def _check_code(cls, value: str | None) -> str | None:
        return _normalize_code(value)


class ProjectUpdate(BaseModel):
    """Partial update: only fields actually present in the request body
    are applied (the router calls .model_dump(exclude_unset=True)) --
    an omitted field means "don't touch it", while an explicit null for
    project_code/description means "clear it". id, company_id, and
    created_at are not present here at all, so there is no field a
    client could set to overwrite them -- not just a check that rejects
    the attempt.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    project_code: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = None

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: str | None) -> str | None:
        return _validate_status(value)

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_name(value)

    @field_validator("project_code")
    @classmethod
    def _check_code(cls, value: str | None) -> str | None:
        return _normalize_code(value)


class ProjectPublic(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    project_code: str | None
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectPage(BaseModel):
    items: list[ProjectPublic]
    next_cursor: str | None

