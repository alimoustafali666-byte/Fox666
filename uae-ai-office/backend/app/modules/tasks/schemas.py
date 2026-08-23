import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.tasks.models import TASK_PRIORITIES, TASK_SOURCE_TYPES, TASK_STATUSES


def _normalize_required_text(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("must not be blank")
    return trimmed


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=8000)
    project_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    priority: str = "normal"
    due_date: date | None = None
    source_type: str = "manual"
    source_id: uuid.UUID | None = None

    @field_validator("title")
    @classmethod
    def _check_title(cls, value: str) -> str:
        return _normalize_required_text(value)

    @field_validator("priority")
    @classmethod
    def _check_priority(cls, value: str) -> str:
        if value not in TASK_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(TASK_PRIORITIES)}")
        return value

    @field_validator("source_type")
    @classmethod
    def _check_source_type(cls, value: str) -> str:
        if value not in TASK_SOURCE_TYPES:
            raise ValueError(f"source_type must be one of {sorted(TASK_SOURCE_TYPES)}")
        return value


class TaskUpdate(BaseModel):
    """Every field optional -- exclude_unset drives which are actually
    considered a change. completed_at is deliberately absent: it is
    always server-derived from a status transition, never client-set.
    """

    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=8000)
    status: str | None = None
    priority: str | None = None
    assigned_to: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def _check_title(cls, value: str | None) -> str | None:
        return _normalize_required_text(value) if value is not None else None

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: str | None) -> str | None:
        if value is not None and value not in TASK_STATUSES:
            raise ValueError(f"status must be one of {sorted(TASK_STATUSES)}")
        return value

    @field_validator("priority")
    @classmethod
    def _check_priority(cls, value: str | None) -> str | None:
        if value is not None and value not in TASK_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(TASK_PRIORITIES)}")
        return value


class TaskPublic(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    project_id: uuid.UUID | None
    project_name: str | None
    title: str
    description: str | None
    status: str
    priority: str
    assigned_to: uuid.UUID | None
    assignee_name: str | None
    created_by: uuid.UUID
    creator_name: str | None
    source_type: str
    source_id: uuid.UUID | None
    due_date: date | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskPage(BaseModel):
    items: list[TaskPublic]
    next_cursor: str | None


class TaskCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body")
    @classmethod
    def _check_body(cls, value: str) -> str:
        return _normalize_required_text(value)


class TaskCommentPublic(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    author_user_id: uuid.UUID
    author_name: str | None
    body: str
    created_at: datetime


class TaskActivityPublic(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_name: str | None
    event_type: str
    field_name: str | None
    old_value: str | None
    new_value: str | None
    created_at: datetime


class TaskDashboardSummary(BaseModel):
    my_open_tasks: int
    due_today: int
    overdue: int
    high_priority_open: int

