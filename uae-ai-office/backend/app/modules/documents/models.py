import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, ForeignKey, ForeignKeyConstraint, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Must match migration 0012's `vector(1024)` column definition exactly.
# Every configured EmbeddingProvider's .dimension is validated against
# this at provider-construction time (app.core.embeddings.factory) --
# changing it requires a new migration to alter the column, not just an
# environment variable, precisely so a dimension mismatch fails loudly
# rather than silently storing something incompatible.
EMBEDDING_VECTOR_DIMENSION = 1024

# Single source of truth, reused by both the DB enum below and
# app.modules.documents' request-validation / filter-validation code --
# mirrors PROJECT_STATUSES in app.modules.projects.models.
DOCUMENT_TYPES: tuple[str, ...] = (
    "contract", "boq", "quotation", "invoice", "purchase_order",
    "project_report", "other",
)

# Plain TEXT, not a DB enum (see the `status` column note below) --
# reused by app.modules.documents' processing orchestration and by
# request/filter validation, the same way DOCUMENT_TYPES is.
DOCUMENT_STATUSES: tuple[str, ...] = ("uploaded", "processing", "processed", "failed")

# A separate lifecycle from DOCUMENT_STATUSES: a document can be fully
# `processed` while still `not_indexed` (no embeddings, not retrievable
# yet). See migration 0013's docstring for why this isn't folded into
# `status`.
DOCUMENT_INDEXING_STATUSES: tuple[str, ...] = ("not_indexed", "indexing", "indexed", "failed")

document_type = ENUM(
    *DOCUMENT_TYPES,
    name="document_type",
    create_type=False,  # created explicitly in the migration
)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        # Composite FK against projects(id, company_id): if project_id is
        # set, its company_id MUST match this row's company_id, enforced by
        # Postgres itself -- a document can never reference another
        # company's project, even if application code has a bug. NULL
        # project_id (company-level documents) bypasses this check entirely
        # (Postgres MATCH SIMPLE semantics), which is the intended behavior.
        ForeignKeyConstraint(
            ["project_id", "company_id"],
            ["projects.id", "projects.company_id"],
            name="fk_documents_project_company",
        ),
        # Referenced by document_chunks' composite FK, added in migration
        # 0010, so a chunk can never claim a company_id that doesn't match
        # its document's real company (see document_chunks' model/migration).
        UniqueConstraint("id", "company_id", name="uq_documents_id_company"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    file_name: Mapped[str]
    file_type: Mapped[str]
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str]
    document_type: Mapped[str] = mapped_column(document_type, server_default="other")
    # Kept as free text (not an enum) so future ingestion states
    # (processing/processed/failed) can be added without a migration to
    # widen a constraint. Phase 1 only ever writes 'uploaded'.
    status: Mapped[str] = mapped_column(server_default="uploaded")
    checksum_sha256: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Bounded, safe strings only -- never a raw parser/vendor stack
    # trace. See app.modules.documents.processing_errors for the closed
    # set of codes and the length cap enforced before either is written.
    processing_error_code: Mapped[str | None] = mapped_column(nullable=True)
    processing_error_message: Mapped[str | None] = mapped_column(nullable=True)
    # Indexing (embeddings) lifecycle -- see DOCUMENT_INDEXING_STATUSES.
    indexing_status: Mapped[str] = mapped_column(server_default="not_indexed")
    indexing_error_code: Mapped[str | None] = mapped_column(nullable=True)
    indexing_error_message: Mapped[str | None] = mapped_column(nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class DocumentChunk(Base):
    """Deterministic output of the Step 9 processing pipeline
    (extract -> normalize -> chunk), plus the Step 10 embedding for that
    same chunk once indexed. `embedding` is NULL until indexed;
    `embedding_model` records exactly which model produced it, so
    retrieval (app.modules.documents.retrieval_service) can compare a
    query embedding only against chunks embedded by the *currently
    configured* model -- a chunk left over from a previous model never
    silently mixes into results just because it happens to be
    dimensionally compatible.

    DOCUMENT CONTENT IS DATA, NOT INSTRUCTIONS. `content` holds text
    extracted from a user-uploaded file; it must never be concatenated
    into a system/instruction prompt or otherwise treated as anything
    other than untrusted retrieved data. Embedding it does not change
    that -- a vector is still a representation of untrusted data, not an
    instruction. This boundary will be enforced again, mechanically,
    wherever this content is later fed to Claude.
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_document_index"),
        # Composite FK against documents(id, company_id) -- see migration
        # 0011's docstring for why this is the only FK constraint on
        # document_id (no separate direct FK to documents.id).
        ForeignKeyConstraint(
            ["document_id", "company_id"],
            ["documents.id", "documents.company_id"],
            name="fk_document_chunks_document_company",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    chunk_index: Mapped[int]
    content: Mapped[str]
    token_count: Mapped[int | None] = mapped_column(nullable=True)
    page_number: Mapped[int | None] = mapped_column(nullable=True)
    sheet_name: Mapped[str | None] = mapped_column(nullable=True)
    section_name: Mapped[str | None] = mapped_column(nullable=True)
    source_location: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    content_hash: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_VECTOR_DIMENSION), nullable=True
    )
    embedding_model: Mapped[str | None] = mapped_column(nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(nullable=True)

