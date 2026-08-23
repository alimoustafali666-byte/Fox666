"""Synchronous indexing pipeline: processed document chunks -> embeddings
-> pgvector persistence. No background worker -- this all runs inline
within the triggering HTTP request, per Step 10's scope. Structurally
mirrors processing_orchestrator.py.

DOCUMENT CONTENT IS DATA, NOT INSTRUCTIONS. Embedding chunk content does
not change that boundary -- a vector is still a representation of
untrusted retrieved data, never an instruction.

Atomicity / re-indexing: mark_document_indexing() is committed
immediately (a small, non-destructive transition -- existing embeddings
are untouched by it), then every chunk's embedding is generated and
validated using only in-memory data plus the embedding provider,
touching the database not at all. Only once every chunk's vector has
been generated AND validated (right count, right dimension) does
persist_chunk_embeddings() run -- updating the existing chunk rows in
the same transaction as marking the document indexed, committed
together. If anything raises before that point, no embedding has been
touched: whatever vectors existed before this call (from an earlier
successful index, if any) are exactly what's still there after a failed
re-index.

Stale-embedding invalidation: this module does not need to invalidate
embeddings when a document's chunks change -- that already happens by
construction in processing_orchestrator.py, which deletes the old chunk
rows entirely (and with them, any embedding columns they carried) before
inserting the new set, and explicitly resets indexing_status back to
'not_indexed' whenever that happens (see repository.mark_document_processed).
A document can therefore never be `indexed` while holding embeddings for
chunk content that no longer exists.
"""

import logging
import time
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.embeddings.exceptions import EmbeddingError, EmbeddingOperationError
from app.core.embeddings.factory import get_embedding_provider
from app.core.embeddings.provider import EmbeddingProvider
from app.modules.audit_log.service import record_audit_event
from app.modules.documents import repository
from app.modules.documents.exceptions import (
    DocumentIndexingFailedError,
    DocumentIndexingUnavailableError,
    DocumentNoChunksToIndexError,
    DocumentNotFoundError,
    DocumentNotProcessedError,
)
from app.modules.documents.models import Document, DocumentChunk

logger = logging.getLogger(__name__)

_MAX_ERROR_MESSAGE_LENGTH = 500
_GENERIC_UNEXPECTED_ERROR_MESSAGE = "An unexpected error occurred while indexing this document."

_API_ERROR_BY_EMBEDDING_ERROR_CODE: dict[str, type] = {
    "embedding_provider_unavailable": DocumentIndexingUnavailableError,
    "embedding_provider_authentication_failed": DocumentIndexingUnavailableError,
    "embedding_provider_misconfigured": DocumentIndexingUnavailableError,
    "embedding_operation_failed": DocumentIndexingFailedError,
}


def index_document(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    document_id: uuid.UUID,
    ip_address: str | None = None,
) -> Document:
    document = repository.get_document_by_id(db, company_id=company_id, document_id=document_id)
    if document is None:
        raise DocumentNotFoundError("Document not found.")

    if document.status != "processed":
        raise DocumentNotProcessedError(
            "Document must be fully processed before it can be indexed."
        )

    chunks = repository.list_document_chunks(db, company_id=company_id, document_id=document.id)
    if not chunks:
        raise DocumentNoChunksToIndexError("Document has no chunks to index.")

    previous_indexing_status = document.indexing_status
    is_reindex = previous_indexing_status in ("indexed", "failed")

    repository.mark_document_indexing(db, document)
    record_audit_event(
        db,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="document.indexing_started",
        resource_type="document",
        resource_id=document.id,
        metadata={
            "document_type": document.document_type,
            "chunk_count": len(chunks),
            "previous_indexing_status": previous_indexing_status,
        },
        ip_address=ip_address,
    )
    db.commit()

    started_at = time.monotonic()
    provider = get_embedding_provider()
    try:
        vectors = _embed_all_chunks(provider, chunks)
    except EmbeddingError as exc:
        _fail(
            db, document=document, company_id=company_id, actor_user_id=actor_user_id,
            ip_address=ip_address, started_at=started_at,
            error_code=exc.error_code, error_message=str(exc)[:_MAX_ERROR_MESSAGE_LENGTH],
        )
        api_error_cls = _API_ERROR_BY_EMBEDDING_ERROR_CODE.get(exc.error_code, DocumentIndexingFailedError)
        raise api_error_cls("This document could not be indexed.") from exc
    except Exception as exc:  # deliberately broad: last-resort safety net -- an unexpected
        # failure anywhere in the pipeline must still transition the document to
        # 'failed' rather than leaving it stuck in 'indexing' indefinitely, and
        # must never leak the raw exception text.
        _fail(
            db, document=document, company_id=company_id, actor_user_id=actor_user_id,
            ip_address=ip_address, started_at=started_at,
            error_code="indexing_failed", error_message=_GENERIC_UNEXPECTED_ERROR_MESSAGE,
        )
        logger.exception("Unexpected error while indexing document %s", document.id)
        raise DocumentIndexingFailedError("This document could not be indexed.") from exc

    duration_ms = int((time.monotonic() - started_at) * 1000)

    repository.persist_chunk_embeddings(
        db, chunks=chunks, vectors=vectors, embedding_model=provider.model_identifier
    )
    repository.mark_document_indexed(db, document)
    record_audit_event(
        db,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="document.indexing_succeeded",
        resource_type="document",
        resource_id=document.id,
        metadata={
            "document_type": document.document_type,
            "chunk_count": len(chunks),
            "embedding_model": provider.model_identifier,
            "duration_ms": duration_ms,
        },
        ip_address=ip_address,
    )
    if is_reindex:
        record_audit_event(
            db,
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="document.reindexed",
            resource_type="document",
            resource_id=document.id,
            metadata={"previous_indexing_status": previous_indexing_status, "chunk_count": len(chunks)},
            ip_address=ip_address,
        )
    db.commit()

    return document


def _embed_all_chunks(
    provider: EmbeddingProvider, chunks: list[DocumentChunk]
) -> list[list[float]]:
    """Pure in-memory work over already-fetched ORM objects plus calls to
    the embedding provider -- no database writes at all, so a failure
    anywhere in this function leaves the database exactly as it was
    after mark_document_indexing()'s commit. Embeds `chunk.content`
    only -- never storage_key, audit metadata, or anything else.
    """
    vectors: list[list[float]] = []
    batch_size = max(1, settings.embedding_batch_size)

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        texts = [chunk.content for chunk in batch]
        batch_vectors = provider.embed_batch(texts)

        if len(batch_vectors) != len(texts):
            raise EmbeddingOperationError(
                "Embedding provider returned an unexpected number of vectors."
            )
        for vector in batch_vectors:
            if len(vector) != provider.dimension:
                raise EmbeddingOperationError(
                    "Embedding provider returned a vector of unexpected dimension."
                )
        vectors.extend(batch_vectors)

    return vectors


def _fail(
    db: Session,
    *,
    document: Document,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    ip_address: str | None,
    started_at: float,
    error_code: str,
    error_message: str,
) -> None:
    """Nothing in the database has been touched since
    mark_document_indexing()'s own commit, so there is nothing to roll
    back here -- this only records the failure and leaves any existing
    (older, still-good) embedding set completely untouched.
    """
    duration_ms = int((time.monotonic() - started_at) * 1000)
    repository.mark_document_indexing_failed(
        db, document, error_code=error_code, error_message=error_message
    )
    record_audit_event(
        db,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="document.indexing_failed",
        resource_type="document",
        resource_id=document.id,
        metadata={
            "document_type": document.document_type,
            "failure_category": error_code,
            "duration_ms": duration_ms,
        },
        ip_address=ip_address,
    )
    db.commit()

