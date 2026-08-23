import logging
import uuid
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage.exceptions import ObjectNotFoundError, StorageError
from app.core.storage.factory import get_storage_provider
from app.core.storage.keys import build_document_object_key
from app.core.storage.provider import StorageProvider
from app.modules.audit_log.service import record_audit_event
from app.modules.documents import repository
from app.modules.documents.content_validation import detect_and_validate_content_type
from app.modules.documents.exceptions import (
    DocumentNotFoundError,
    DocumentStorageUnavailableError,
    InvalidDocumentTypeError,
)
from app.modules.documents.filenames import sanitize_filename
from app.modules.documents.models import DOCUMENT_TYPES, Document
from app.modules.documents.upload_stream import measure_and_checksum
from app.modules.projects import repository as projects_repository
from app.modules.projects.exceptions import ProjectNotFoundError

logger = logging.getLogger(__name__)


def _compensate_storage_delete(provider: StorageProvider, storage_key: str) -> None:
    """Best-effort cleanup of an object that was successfully stored but
    whose database row / audit event failed to commit. Never raises: a
    failed compensation must not mask the original failure, and there is
    no background worker (yet) to retry it -- this is logged so an
    orphaned object stays observable for future manual/automated cleanup.
    """
    try:
        provider.delete(key=storage_key)
    except StorageError:
        logger.exception(
            "Compensating delete failed after a failed document upload; "
            "an orphaned storage object may exist at key=%s",
            storage_key,
        )


def upload_document(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    project_id: uuid.UUID | None,
    document_type: str,
    upload_file,  # fastapi.UploadFile-shaped: .filename (str), .file (BinaryIO)
    ip_address: str | None = None,
) -> Document:
    if document_type not in DOCUMENT_TYPES:
        raise InvalidDocumentTypeError(f"document_type must be one of {sorted(DOCUMENT_TYPES)}.")

    if project_id is not None:
        # Same IDOR-safe lookup Projects itself uses: a project belonging
        # to another company is indistinguishable from one that doesn't
        # exist. No status filter -- a cancelled project may still hold
        # documents (explicitly approved; not stricter than that).
        project = projects_repository.get_project_by_id(
            db, company_id=company_id, project_id=project_id
        )
        if project is None:
            raise ProjectNotFoundError("Project not found.")

    document_id = uuid.uuid4()
    storage_key = build_document_object_key(company_id=company_id, document_id=document_id)
    sanitized_filename = sanitize_filename(upload_file.filename)

    fileobj: BinaryIO = upload_file.file
    size_bytes, checksum_sha256 = measure_and_checksum(
        fileobj, max_bytes=settings.storage_max_upload_bytes
    )
    content_type = detect_and_validate_content_type(filename=sanitized_filename, fileobj=fileobj)

    provider = get_storage_provider()
    try:
        fileobj.seek(0)
        provider.upload(key=storage_key, data=fileobj, content_type=content_type)
    except StorageError as exc:
        raise DocumentStorageUnavailableError(
            "Unable to store the uploaded document right now."
        ) from exc

    try:
        document = repository.create_document(
            db,
            id=document_id,
            company_id=company_id,
            project_id=project_id,
            uploaded_by=actor_user_id,
            file_name=sanitized_filename,
            file_type=content_type,
            file_size_bytes=size_bytes,
            storage_key=storage_key,
            document_type=document_type,
            checksum_sha256=checksum_sha256,
        )
        record_audit_event(
            db,
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="document.upload",
            resource_type="document",
            resource_id=document.id,
            metadata={
                "document_type": document_type,
                "project_id": str(project_id) if project_id else None,
                "file_size_bytes": size_bytes,
            },
            ip_address=ip_address,
        )
        db.commit()
    except Exception:
        db.rollback()
        _compensate_storage_delete(provider, storage_key)
        raise

    return document


def get_document(db: Session, *, company_id: uuid.UUID, document_id: uuid.UUID) -> Document:
    document = repository.get_document_by_id(db, company_id=company_id, document_id=document_id)
    if document is None:
        raise DocumentNotFoundError("Document not found.")
    return document


def list_documents(
    db: Session,
    *,
    company_id: uuid.UUID,
    limit: int,
    cursor: tuple | None,
    project_id: uuid.UUID | None,
    document_type: str | None,
    status: str | None,
    filename_search: str | None,
) -> list[Document]:
    return repository.list_documents(
        db,
        company_id=company_id,
        limit=limit,
        cursor=cursor,
        project_id=project_id,
        document_type=document_type,
        status=status,
        filename_search=filename_search,
    )


def get_document_download_url(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    document_id: uuid.UUID,
    ip_address: str | None = None,
) -> tuple[str, int]:
    """Authoritative flow: authenticated + tenant-scoped document lookup
    first, then (and only then) a signed URL for THAT document's own
    internal storage key. There is no code path that accepts a
    client-supplied object key.
    """
    document = repository.get_document_by_id(db, company_id=company_id, document_id=document_id)
    if document is None:
        raise DocumentNotFoundError("Document not found.")

    provider = get_storage_provider()
    try:
        url = provider.generate_download_url(key=document.storage_key)
    except ObjectNotFoundError as exc:
        # The DB row exists but the backing object doesn't -- a
        # DB/storage consistency problem, not a client error. Never
        # expose the raw storage key or the fact that this is a missing
        # object specifically.
        raise DocumentStorageUnavailableError(
            "This document's file is temporarily unavailable."
        ) from exc
    except StorageError as exc:
        raise DocumentStorageUnavailableError(
            "This document's file is temporarily unavailable."
        ) from exc

    # A generated signed URL means download *authorization* was issued,
    # not that the file was actually fetched from storage -- this audit
    # event records the former only.
    record_audit_event(
        db,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="document.download",
        resource_type="document",
        resource_id=document.id,
        metadata={
            "document_type": document.document_type,
            "project_id": str(document.project_id) if document.project_id else None,
        },
        ip_address=ip_address,
    )
    db.commit()

    return url, settings.storage_signed_url_ttl_seconds


def delete_document(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    document_id: uuid.UUID,
    ip_address: str | None = None,
) -> Document:
    """Soft delete only: deleted_at is set, the row and its storage
    object are both left in place (storage cleanup policy is a later
    concern). A document that's already soft-deleted is, by the same
    get_document_by_id lookup every other endpoint uses, indistinguishable
    from one that never existed -- so deleting it again safely returns
    the same 404 as any other not-found document, rather than a special
    "already deleted" case.
    """
    document = repository.get_document_by_id(db, company_id=company_id, document_id=document_id)
    if document is None:
        raise DocumentNotFoundError("Document not found.")

    repository.soft_delete_document(db, document)
    record_audit_event(
        db,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="document.delete",
        resource_type="document",
        resource_id=document.id,
        metadata={"document_type": document.document_type},
        ip_address=ip_address,
    )
    db.commit()
    return document

