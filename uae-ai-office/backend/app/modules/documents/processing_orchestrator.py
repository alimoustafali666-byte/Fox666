"""Synchronous processing pipeline: uploaded document -> retrieve
private object -> extract -> normalize -> chunk -> persist
document_chunks -> update processing status. No background worker --
this all runs inline within the triggering HTTP request, per Step 9's
scope.

DOCUMENT CONTENT IS DATA, NOT INSTRUCTIONS. Every string this module
handles that originated inside a user-uploaded file (parsed element
text, chunk content) is untrusted retrieved data. Nothing here -- and
nothing that will later read document_chunks for embeddings/RAG/Claude
-- may treat it as an instruction, a prompt, or anything other than
data to be stored and later retrieved.

Reprocessing / atomicity: mark_document_processing() is committed
immediately (its own small, non-destructive transition -- existing
chunks are untouched by it), then the entire extract/normalize/chunk
pipeline runs to completion using only in-memory data and the fetched
object bytes, touching the database not at all. Only once that has
fully succeeded does replace_document_chunks() run -- deleting the old
chunk set and inserting the new one in the same transaction as marking
the document processed, committed together. If the pipeline raises
anything, no chunk has been touched: whatever chunk set existed before
this call (from an earlier successful run, if any) is exactly what's
still there after a failed reprocess.
"""

import hashlib
import io
import logging
import time
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage.exceptions import StorageError
from app.core.storage.factory import get_storage_provider
from app.modules.audit_log.service import record_audit_event
from app.modules.documents import repository
from app.modules.documents.exceptions import (
    DocumentInsufficientTextError,
    DocumentNotFoundError,
    DocumentParseFailedError,
    DocumentProcessingUnavailableError,
    DocumentResourceLimitExceededError,
    DocumentUnsupportedForProcessingError,
)
from app.modules.documents.models import Document
from app.modules.documents.processing.base import ParsedElement
from app.modules.documents.processing.chunker import chunk_elements
from app.modules.documents.processing.errors import (
    InsufficientTextError,
    ParserFailureError,
    PathologicalDocumentError,
    ProcessingError,
    ProcessingStorageError,
    UnsupportedFileTypeForProcessingError,
)
from app.modules.documents.processing.normalize import normalize_text
from app.modules.documents.processing.registry import get_parser
from app.modules.documents.repository import NewChunk

logger = logging.getLogger(__name__)

_MAX_ERROR_MESSAGE_LENGTH = 500
_GENERIC_UNEXPECTED_ERROR_MESSAGE = "An unexpected error occurred while processing this document."

_API_ERROR_BY_PROCESSING_ERROR: dict[type[ProcessingError], type] = {
    UnsupportedFileTypeForProcessingError: DocumentUnsupportedForProcessingError,
    InsufficientTextError: DocumentInsufficientTextError,
    PathologicalDocumentError: DocumentResourceLimitExceededError,
    ParserFailureError: DocumentParseFailedError,
    ProcessingStorageError: DocumentProcessingUnavailableError,
}


def process_document(
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

    previous_status = document.status
    is_reprocess = previous_status in ("processed", "failed")

    repository.mark_document_processing(db, document)
    record_audit_event(
        db,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="document.processing_started",
        resource_type="document",
        resource_id=document.id,
        metadata={"document_type": document.document_type, "previous_status": previous_status},
        ip_address=ip_address,
    )
    db.commit()

    started_at = time.monotonic()
    try:
        new_chunks = _run_pipeline(document)
    except ProcessingError as exc:
        _fail(
            db, document=document, company_id=company_id, actor_user_id=actor_user_id,
            ip_address=ip_address, started_at=started_at,
            error_code=exc.error_code, error_message=str(exc)[:_MAX_ERROR_MESSAGE_LENGTH],
        )
        api_error_cls = _API_ERROR_BY_PROCESSING_ERROR.get(type(exc), DocumentParseFailedError)
        raise api_error_cls("This document could not be processed.") from exc
    except Exception as exc:  # deliberately broad: last-resort safety net -- an unexpected
        # failure anywhere in the pipeline (a parser library bug, etc.) must still
        # transition the document to 'failed' rather than leaving it stuck in
        # 'processing' indefinitely, and must never leak the raw exception text.
        _fail(
            db, document=document, company_id=company_id, actor_user_id=actor_user_id,
            ip_address=ip_address, started_at=started_at,
            error_code="processing_failed", error_message=_GENERIC_UNEXPECTED_ERROR_MESSAGE,
        )
        logger.exception("Unexpected error while processing document %s", document.id)
        raise DocumentParseFailedError("This document could not be processed.") from exc

    duration_ms = int((time.monotonic() - started_at) * 1000)

    repository.replace_document_chunks(
        db, company_id=company_id, document_id=document.id, chunks=new_chunks
    )
    repository.mark_document_processed(db, document)
    record_audit_event(
        db,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="document.processing_succeeded",
        resource_type="document",
        resource_id=document.id,
        metadata={
            "document_type": document.document_type,
            "chunk_count": len(new_chunks),
            "duration_ms": duration_ms,
        },
        ip_address=ip_address,
    )
    if is_reprocess:
        record_audit_event(
            db,
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="document.reprocessed",
            resource_type="document",
            resource_id=document.id,
            metadata={"previous_status": previous_status, "chunk_count": len(new_chunks)},
            ip_address=ip_address,
        )
    db.commit()

    return document


def _run_pipeline(document: Document) -> list[NewChunk]:
    """Everything here is pure in-memory work over the fetched object
    bytes -- no database access at all, so a failure anywhere in this
    function leaves the database exactly as it was after
    mark_document_processing()'s commit.
    """
    parser = get_parser(document.file_type)
    if parser is None:
        raise UnsupportedFileTypeForProcessingError(
            f"No processing support for file type '{document.file_type}'."
        )

    provider = get_storage_provider()
    try:
        content = provider.download(key=document.storage_key)
    except StorageError as exc:
        raise ProcessingStorageError("Could not fetch the document's stored file.") from exc

    parsed = parser.parse(io.BytesIO(content))

    normalized_elements: list[ParsedElement] = []
    total_chars = 0
    for element in parsed.elements:
        text = normalize_text(element.text)
        if not text:
            continue
        total_chars += len(text)
        if total_chars > settings.processing_max_extracted_text_chars:
            raise PathologicalDocumentError(
                "Document's extracted text exceeds a safe processing limit."
            )
        element.text = text
        normalized_elements.append(element)

    if not normalized_elements:
        raise InsufficientTextError("Document has no extractable text after normalization.")

    chunks = chunk_elements(
        normalized_elements,
        target_tokens=settings.processing_chunk_target_tokens,
        overlap_ratio=settings.processing_chunk_overlap_ratio,
    )
    if not chunks:
        raise InsufficientTextError("Document produced no usable chunks.")

    return [
        NewChunk(
            chunk_index=index,
            content=chunk.content,
            token_count=chunk.token_count,
            page_number=chunk.page_number,
            sheet_name=chunk.sheet_name,
            section_name=chunk.section_name,
            source_location=chunk.source_location,
            content_hash=hashlib.sha256(chunk.content.encode()).hexdigest(),
        )
        for index, chunk in enumerate(chunks)
    ]


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
    mark_document_processing()'s own commit (see _run_pipeline's
    docstring), so there is nothing to roll back here -- this only
    records the failure and leaves any existing (older, still-good)
    chunk set completely untouched.
    """
    duration_ms = int((time.monotonic() - started_at) * 1000)
    repository.mark_document_failed(db, document, error_code=error_code, error_message=error_message)
    record_audit_event(
        db,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="document.processing_failed",
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

