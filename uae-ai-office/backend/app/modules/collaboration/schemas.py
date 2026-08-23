import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.modules.collaboration.models import (
    ATTACHMENT_KINDS,
    CALL_TYPES,
    NOTIFICATION_PREFS,
)
from app.modules.collaboration.service import ALLOWED_REACTIONS


def _normalize_required_text(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("must not be blank")
    return trimmed


# --- conversations ---


class DirectConversationCreate(BaseModel):
    other_user_id: uuid.UUID


class GroupConversationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    member_user_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        return _normalize_required_text(value)


class ProjectChannelCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    member_user_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        return _normalize_required_text(value)


class ConversationRenameRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class AddMemberRequest(BaseModel):
    user_id: uuid.UUID


class NotificationPrefUpdate(BaseModel):
    pref: str

    @field_validator("pref")
    @classmethod
    def _check_pref(cls, value: str) -> str:
        if value not in NOTIFICATION_PREFS:
            raise ValueError(f"pref must be one of {sorted(NOTIFICATION_PREFS)}")
        return value


class MarkReadRequest(BaseModel):
    message_id: uuid.UUID


class ConversationPublic(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    type: str
    name: str | None
    description: str | None
    project_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    unread_count: int = 0


class ConversationPage(BaseModel):
    items: list[ConversationPublic]
    next_cursor: str | None


class ConversationMemberPublic(BaseModel):
    user_id: uuid.UUID
    full_name: str | None
    role: str
    notification_pref: str
    joined_at: datetime
    last_read_at: datetime | None


# --- messages ---


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=settings.collaboration_message_max_length)
    reply_to_message_id: uuid.UUID | None = None
    shared_document_id: uuid.UUID | None = None


class MessageEditRequest(BaseModel):
    content: str = Field(min_length=1, max_length=settings.collaboration_message_max_length)


class AttachmentPublic(BaseModel):
    id: uuid.UUID
    kind: str
    file_name: str
    file_type: str
    file_size_bytes: int
    duration_seconds: int | None
    created_at: datetime

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, value: str) -> str:
        if value not in ATTACHMENT_KINDS:
            raise ValueError(f"kind must be one of {sorted(ATTACHMENT_KINDS)}")
        return value


class ReactionSummary(BaseModel):
    emoji: str
    user_ids: list[uuid.UUID]


class MessagePublic(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID | None
    sender_name: str | None
    message_type: str
    content: str
    reply_to_message_id: uuid.UUID | None
    shared_document_id: uuid.UUID | None
    edited_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime
    attachments: list[AttachmentPublic] = Field(default_factory=list)
    reactions: list[ReactionSummary] = Field(default_factory=list)


class MessagePage(BaseModel):
    items: list[MessagePublic]
    next_cursor: str | None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=settings.collaboration_search_query_max_length)


class ReactionRequest(BaseModel):
    emoji: str

    @field_validator("emoji")
    @classmethod
    def _check_emoji(cls, value: str) -> str:
        if value not in ALLOWED_REACTIONS:
            raise ValueError(f"emoji must be one of {sorted(ALLOWED_REACTIONS)}")
        return value


class PinnedMessagePublic(BaseModel):
    message_id: uuid.UUID
    pinned_by: uuid.UUID
    pinned_at: datetime


# --- notifications ---


class NotificationPublic(BaseModel):
    id: uuid.UUID
    type: str
    conversation_id: uuid.UUID | None
    message_id: uuid.UUID | None
    support_ticket_id: uuid.UUID | None
    task_id: uuid.UUID | None
    title: str
    body: str | None
    read_at: datetime | None
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationPublic]
    unread_count: int


# --- calls ---


class CallStartRequest(BaseModel):
    call_type: str

    @field_validator("call_type")
    @classmethod
    def _check_call_type(cls, value: str) -> str:
        if value not in CALL_TYPES:
            raise ValueError(f"call_type must be one of {sorted(CALL_TYPES)}")
        return value


class CallRespondRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: str) -> str:
        if value not in ("joined", "declined", "left"):
            raise ValueError("status must be one of ['declined', 'joined', 'left']")
        return value


class CallParticipantPublic(BaseModel):
    user_id: uuid.UUID
    status: str
    joined_at: datetime | None
    left_at: datetime | None


class CallSessionPublic(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    initiated_by: uuid.UUID
    call_type: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    ended_reason: str | None
    participants: list[CallParticipantPublic] = Field(default_factory=list)


# --- AI collaboration ---


class AiQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AiDecisionPublic(BaseModel):
    description: str
    confirmed: bool
    source_message_id: uuid.UUID | None


class AiActionItemPublic(BaseModel):
    description: str
    possible_assignee: str | None
    due_date: str | None
    source_message_id: uuid.UUID | None


class AiInsightsResponse(BaseModel):
    summary: str
    decisions: list[AiDecisionPublic]
    action_items: list[AiActionItemPublic]


class AiCitation(BaseModel):
    message_id: uuid.UUID


class AiAnswerResponse(BaseModel):
    answer: str
    sufficient: bool
    citations: list[AiCitation]

