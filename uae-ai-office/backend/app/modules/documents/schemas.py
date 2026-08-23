import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DocumentPublic(BaseModel):
    """storage_key is deliberately never included here -- it's an
    internal, security-sensitive implementation detail. Signed download
    URLs are generated server-side, on demand, via the dedicated
    /download endpoint; nothing about the underlying object key is ever
    returned to a client.
    """

    id: uuid.UUID
    company_id: uuid.UUID
    project_id: uuid.UUID | None
    uploaded_by: uuid.UUID
    file_name: str
    file_type: str
    file_size_bytes: int
    document_type: str
    status: str
    checksum_sha256: str
    # Bounded, safe strings only (see app.modules.documents.processing.errors)
    # -- never a raw parser/vendor stack trace. Both are null unless
    # status == "failed".
    processing_error_code: str | None
    processing_error_message: str | None
    # Separate lifecycle from status/processing_error_* -- see
    # DOCUMENT_INDEXING_STATUSES. Both error fields are null unless
    # indexing_status == "failed".
    indexing_status: str
    indexing_error_code: str | None
    indexing_error_message: str | None
    created_at: datetime
    updated_at: datetime


class DocumentPage(BaseModel):
    items: list[DocumentPublic]
    next_cursor: str | None


class DocumentDownloadResponse(BaseModel):
    download_url: str
    expires_in_seconds: int


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1)
    document_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    document_type: str | None = None


class SearchResultItem(BaseModel):
    """Deliberately excludes the embedding vector and storage_key --
    neither is ever returned by this or any endpoint. `score` is cosine
    similarity (1 - pgvector cosine_distance); see retrieval_service.py.
    """

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    score: float
    page_number: int | None
    sheet_name: str | None
    section_name: str | None
    source_location: dict | None


class SearchResponse(BaseModel):
    items: list[SearchResultItem]

