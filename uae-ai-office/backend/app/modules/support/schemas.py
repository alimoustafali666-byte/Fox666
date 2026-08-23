import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.modules.support.diagnostics import DiagnosticsInput
from app.modules.support.models import (
    SUPPORT_TICKET_CATEGORIES,
    SUPPORT_TICKET_PRIORITIES,
    SUPPORT_TICKET_STATUSES,
)


def _validate_category(value: str) -> str:
    if value not in SUPPORT_TICKET_CATEGORIES:
        raise ValueError(f"category must be one of {sorted(SUPPORT_TICKET_CATEGORIES)}")
    return value


def _validate_priority(value: str) -> str:
    if value not in SUPPORT_TICKET_PRIORITIES:
        raise ValueError(f"priority must be one of {sorted(SUPPORT_TICKET_PRIORITIES)}")
    return value


def _normalize_required_text(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("must not be blank")
    return trimmed


class SupportTicketCreate(BaseModel):
    category: str
    subject: str = Field(min_length=1, max_length=settings.support_ticket_subject_max_length)
    description: str = Field(
        min_length=1, max_length=settings.support_ticket_description_max_length
    )
    priority: str = "normal"
    diagnostics: DiagnosticsInput | None = None

    @field_validator("category")
    @classmethod
    def _check_category(cls, value: str) -> str:
        return _validate_category(value)

    @field_validator("priority")
    @classmethod
    def _check_priority(cls, value: str) -> str:
        return _validate_priority(value)

    @field_validator("subject")
    @classmethod
    def _check_subject(cls, value: str) -> str:
        return _normalize_required_text(value)

    @field_validator("description")
    @classmethod
    def _check_description(cls, value: str) -> str:
        return _normalize_required_text(value)


class SupportTicketStatusUpdate(BaseModel):
    """Step 17 only exposes creator self-service closing of their own
    ticket -- see app.modules.support.service.update_ticket_status for
    why every other status transition is rejected (no support-admin
    actor exists yet to legitimately drive them).
    """

    status: str

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: str) -> str:
        if value not in SUPPORT_TICKET_STATUSES:
            raise ValueError(f"status must be one of {sorted(SUPPORT_TICKET_STATUSES)}")
        return value


class SupportTicketCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=settings.support_ticket_comment_max_length)

    @field_validator("body")
    @classmethod
    def _check_body(cls, value: str) -> str:
        return _normalize_required_text(value)


class SupportTicketCommentPublic(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    author_type: str
    author_user_id: uuid.UUID | None
    body: str
    created_at: datetime


class SupportTicketPublic(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    created_by: uuid.UUID
    category: str
    subject: str
    description: str
    priority: str
    status: str
    reference_code: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class SupportTicketDetail(SupportTicketPublic):
    comments: list[SupportTicketCommentPublic]


class SupportTicketPage(BaseModel):
    items: list[SupportTicketPublic]
    next_cursor: str | None


class SupportArticlePublic(BaseModel):
    slug: str
    category: str
    title: str
    body: str


class SupportArticlePage(BaseModel):
    items: list[SupportArticlePublic]


class SupportSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=settings.support_kb_query_max_length)


class SupportAssistantAskRequest(BaseModel):
    question: str = Field(
        min_length=1, max_length=settings.support_assistant_question_max_length
    )
    diagnostics: DiagnosticsInput | None = None


class SupportAssistantCitation(BaseModel):
    article_slug: str
    title: str


class SupportAssistantAskResponse(BaseModel):
    answer: str
    sufficient: bool
    citations: list[SupportAssistantCitation]
    used_diagnostics: bool

