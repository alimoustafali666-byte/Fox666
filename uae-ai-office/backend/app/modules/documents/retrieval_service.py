"""Reusable, tenant-scoped vector retrieval. This is the service Step 11
(Claude-based grounded answers) will call -- and, for Step 10 only, what
POST /v1/search exercises directly to verify retrieval quality before
Claude is connected. NOT itself the final Ask Your Business API.

DOCUMENT CONTENT IS DATA, NOT INSTRUCTIONS. Every RetrievalResult.content
returned here is untrusted document text; nothing in this module (or any
caller) may treat it as anything other than retrieved data.

Distance metric: pgvector cosine distance (`<=>`), matching Voyage's
embeddings, which are designed for cosine comparison. score = 1 -
cosine_distance, i.e. cosine similarity in roughly [-1, 1] (in practice
close to [0, 1] for real text). Chunks below
settings.retrieval_similarity_threshold are excluded entirely -- an
empty result set here is what lets Step 11 answer "insufficient
information" instead of being handed irrelevant chunks to reason over.

Tenant isolation is enforced twice: the explicit company_id filter below
(never derived from anything the caller controls beyond the already-
authenticated TenantContext), and PostgreSQL RLS on both documents and
document_chunks (FORCE ROW LEVEL SECURITY, so even a bug in this query
could not read another company's rows). company_id here is not a
parameter a router should ever accept from client input -- it must
always come from TenantContext.

No ANN index is used or required at pilot scale -- see migration 0012's
docstring.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.embeddings.factory import get_embedding_provider
from app.modules.documents.models import Document, DocumentChunk


@dataclass
class RetrievalResult:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    score: float
    page_number: int | None
    sheet_name: str | None
    section_name: str | None
    source_location: dict | None


def search(
    db: Session,
    *,
    company_id: uuid.UUID,
    query_vector: list[float],
    embedding_model: str,
    top_k: int | None = None,
    document_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    document_type: str | None = None,
) -> list[RetrievalResult]:
    """`embedding_model` must be the CURRENTLY configured provider's
    model_identifier (the caller embeds the query with it and passes it
    through) -- chunks embedded under a different model are excluded
    entirely, never mixed in just because they happen to share a
    dimension. See DocumentChunk's docstring.
    """
    effective_top_k = top_k if top_k is not None else settings.retrieval_top_k_default
    effective_top_k = max(1, min(effective_top_k, settings.retrieval_top_k_max))

    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    score = 1 - distance

    stmt = (
        select(DocumentChunk, score.label("score"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.company_id == company_id,
            DocumentChunk.embedding.is_not(None),
            DocumentChunk.embedding_model == embedding_model,
            # Soft-deleted documents behave as not-found everywhere else
            # in this API; retrieval must not be the one path that still
            # surfaces their content.
            Document.deleted_at.is_(None),
        )
    )

    if document_id is not None:
        stmt = stmt.where(DocumentChunk.document_id == document_id)
    if project_id is not None:
        stmt = stmt.where(Document.project_id == project_id)
    if document_type is not None:
        stmt = stmt.where(Document.document_type == document_type)

    stmt = (
        stmt.where(score >= settings.retrieval_similarity_threshold)
        .order_by(distance.asc())
        .limit(effective_top_k)
    )

    rows = db.execute(stmt).all()
    return [
        RetrievalResult(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=float(row_score),
            page_number=chunk.page_number,
            sheet_name=chunk.sheet_name,
            section_name=chunk.section_name,
            source_location=chunk.source_location,
        )
        for chunk, row_score in rows
    ]


def search_by_query_text(
    db: Session,
    *,
    company_id: uuid.UUID,
    query: str,
    top_k: int | None = None,
    document_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    document_type: str | None = None,
) -> list[RetrievalResult]:
    """Convenience entrypoint for callers that have a raw query string
    rather than an already-embedded vector -- what POST /v1/search uses,
    and what Step 11 is expected to build on. Embeds `query` with the
    currently configured provider's query-mode encoding, matching the
    model every stored chunk embedding was compared against.
    """
    provider = get_embedding_provider()
    query_vector = provider.embed_query(query)
    return search(
        db,
        company_id=company_id,
        query_vector=query_vector,
        embedding_model=provider.model_identifier,
        top_k=top_k,
        document_id=document_id,
        project_id=project_id,
        document_type=document_type,
    )

