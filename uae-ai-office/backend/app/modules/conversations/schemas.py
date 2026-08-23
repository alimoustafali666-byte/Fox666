import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)


class ConversationPublic(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    created_by: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationPage(BaseModel):
    items: list[ConversationPublic]
    next_cursor: str | None


class AskRequest(BaseModel):
    """Deliberately excludes (via extra="forbid") company_id, retrieved
    chunks, a system prompt, role, model, or any storage key -- none of
    those are ever accepted from the client. company_id always comes
    from TenantContext; retrieval, the system prompt, and the model are
    entirely server-controlled. The optional filters below narrow
    *which already-authorized* documents retrieval may consider -- they
    can never widen access or bypass the similarity threshold.
    """

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=0, max_length=10_000)
    document_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    document_type: str | None = None


class CitationPublic(BaseModel):
    """Deliberately excludes storage_key, the embedding vector, and any
    signed URL -- never returned by this or any endpoint.
    """

    document_chunk_id: uuid.UUID
    document_id: uuid.UUID
    file_name: str
    document_type: str
    project_id: uuid.UUID | None
    page_number: int | None
    sheet_name: str | None
    section_name: str | None
    source_location: dict | None


class MessagePublic(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    is_sufficient: bool | None
    model_identifier: str | None
    created_at: datetime
    citations: list[CitationPublic]


class MessagePage(BaseModel):
    items: list[MessagePublic]
    next_cursor: str | None

