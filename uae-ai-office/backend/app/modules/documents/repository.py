import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.modules.documents.models import Document, DocumentChunk


def create_document(
    db: Session,
    *,
    id: uuid.UUID,
    company_id: uuid.UUID,
    project_id: uuid.UUID | None,
    uploaded_by: uuid.UUID,
    file_name: str,
    file_type: str,
    file_size_bytes: int,
    storage_key: str,
    document_type: str,
    checksum_sha256: str,
) -> Document:
    document = Document(
        id=id,
        company_id=company_id,
        project_id=project_id,
        uploaded_by=uploaded_by,
        file_name=file_name,
        file_type=file_type,
        file_size_bytes=file_size_bytes,
        storage_key=storage_key,
        document_type=document_type,
        checksum_sha256=checksum_sha256,
    )
    db.add(document)
    db.flush()
    return document


def get_document_by_id(
    db: Session, *, company_id: uuid.UUID, document_id: uuid.UUID
) -> Document | None:
    """Explicit company_id filter is defense in depth on top of RLS (see
    the tenant_isolation policy on `documents`), and excluding
    soft-deleted rows here means every caller -- get, download, delete --
    automatically treats "soft-deleted" the same as "doesn't exist",
    without needing to remember to check deleted_at separately.
    """
    return db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
            Document.deleted_at.is_(None),
        )
    ).scalar_one_or_none()


def list_documents(
    db: Session,
    *,
    company_id: uuid.UUID,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None = None,
    project_id: uuid.UUID | None = None,
    document_type: str | None = None,
    status: str | None = None,
    filename_search: str | None = None,
) -> list[Document]:
    query = select(Document).where(
        Document.company_id == company_id, Document.deleted_at.is_(None)
    )

    if project_id is not None:
        query = query.where(Document.project_id == project_id)
    if document_type is not None:
        query = query.where(Document.document_type == document_type)
    if status is not None:
        query = query.where(Document.status == status)
    if filename_search is not None:
        query = query.where(Document.file_name.ilike(f"%{filename_search}%"))
    if cursor is not None:
        cursor_created_at, cursor_id = cursor
        query = query.where(
            or_(
                Document.created_at < cursor_created_at,
                and_(Document.created_at == cursor_created_at, Document.id < cursor_id),
            )
        )

    query = query.order_by(Document.created_at.desc(), Document.id.desc()).limit(limit)
    return list(db.execute(query).scalars())


def soft_delete_document(db: Session, document: Document) -> Document:
    now = datetime.now(UTC)
    document.deleted_at = now
    document.updated_at = now
    db.flush()
    return document


def mark_document_processing(db: Session, document: Document) -> Document:
    document.status = "processing"
    document.processing_error_code = None
    document.processing_error_message = None
    document.updated_at = datetime.now(UTC)
    db.flush()
    return document


def mark_document_processed(db: Session, document: Document) -> Document:
    document.status = "processed"
    document.processing_error_code = None
    document.processing_error_message = None
    document.updated_at = datetime.now(UTC)
    # Every call site replaces the chunk set (see replace_document_chunks)
    # before this runs -- any previously-indexed embeddings were carried
    # on the now-deleted chunk rows and are gone with them, so the
    # indexing lifecycle must revert to not_indexed rather than keep
    # claiming a chunk set that no longer exists is "indexed". See the
    # Step 10 report's stale-embedding-invalidation section.
    document.indexing_status = "not_indexed"
    document.indexing_error_code = None
    document.indexing_error_message = None
    document.indexed_at = None
    db.flush()
    return document


def mark_document_failed(
    db: Session, document: Document, *, error_code: str, error_message: str
) -> Document:
    document.status = "failed"
    document.processing_error_code = error_code
    document.processing_error_message = error_message
    document.updated_at = datetime.now(UTC)
    db.flush()
    return document


@dataclass
class NewChunk:
    """What the orchestrator hands the repository once a processing
    attempt has fully succeeded -- everything needed to insert one
    document_chunks row except the ids the repository itself assigns.
    """

    chunk_index: int
    content: str
    token_count: int | None
    page_number: int | None
    sheet_name: str | None
    section_name: str | None
    source_location: dict | None
    content_hash: str


def count_document_chunks(db: Session, *, company_id: uuid.UUID, document_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count()).select_from(DocumentChunk).where(
            DocumentChunk.company_id == company_id, DocumentChunk.document_id == document_id
        )
    ).scalar_one()


def replace_document_chunks(
    db: Session, *, company_id: uuid.UUID, document_id: uuid.UUID, chunks: list[NewChunk]
) -> list[DocumentChunk]:
    """Atomically replaces the full chunk set for one document: deletes
    whatever is currently there and inserts the new set, in the same
    transaction the caller commits. Only ever called by the orchestrator
    after a processing attempt has already fully succeeded (parsing,
    normalization, and chunking all completed) -- so a chunk set that
    was good is never removed on the strength of an attempt that might
    still fail; see processing_orchestrator.py.
    """
    db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.company_id == company_id, DocumentChunk.document_id == document_id
        )
    )

    rows = [
        DocumentChunk(
            company_id=company_id,
            document_id=document_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            token_count=chunk.token_count,
            page_number=chunk.page_number,
            sheet_name=chunk.sheet_name,
            section_name=chunk.section_name,
            source_location=chunk.source_location,
            content_hash=chunk.content_hash,
        )
        for chunk in chunks
    ]
    db.add_all(rows)
    db.flush()
    return rows


def list_document_chunks(
    db: Session, *, company_id: uuid.UUID, document_id: uuid.UUID
) -> list[DocumentChunk]:
    return list(
        db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.company_id == company_id, DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        ).scalars()
    )


def mark_document_indexing(db: Session, document: Document) -> Document:
    document.indexing_status = "indexing"
    document.indexing_error_code = None
    document.indexing_error_message = None
    document.updated_at = datetime.now(UTC)
    db.flush()
    return document


def mark_document_indexed(db: Session, document: Document) -> Document:
    now = datetime.now(UTC)
    document.indexing_status = "indexed"
    document.indexing_error_code = None
    document.indexing_error_message = None
    document.indexed_at = now
    document.updated_at = now
    db.flush()
    return document


def mark_document_indexing_failed(
    db: Session, document: Document, *, error_code: str, error_message: str
) -> Document:
    document.indexing_status = "failed"
    document.indexing_error_code = error_code
    document.indexing_error_message = error_message
    document.updated_at = datetime.now(UTC)
    db.flush()
    return document


def persist_chunk_embeddings(
    db: Session,
    *,
    chunks: list[DocumentChunk],
    vectors: list[list[float]],
    embedding_model: str,
) -> None:
    """Only ever called by the indexing orchestrator after every vector
    has already been generated AND validated (right count, right
    dimension) -- see indexing_orchestrator.py. `chunks` and `vectors`
    must be the same length and in the same order (the caller's
    responsibility; this function trusts it and does not re-validate).
    Updates the existing chunk rows in place -- chunk identity
    (id/chunk_index/content/content_hash/source_location) is untouched,
    only the embedding-specific columns change.
    """
    now = datetime.now(UTC)
    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk.embedding = vector
        chunk.embedding_model = embedding_model
        chunk.embedded_at = now
    db.flush()

