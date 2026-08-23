import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError
from app.core.pagination import InvalidCursorError, decode_cursor, encode_cursor
from app.core.request_ip import get_client_ip
from app.db.session import get_db
from app.modules.auth.dependencies import get_tenant_context, require_roles
from app.modules.auth.service import TenantContext
from app.modules.documents import indexing_orchestrator, processing_orchestrator, service
from app.modules.documents.models import DOCUMENT_TYPES, Document
from app.modules.documents.schemas import (
    DocumentDownloadResponse,
    DocumentPage,
    DocumentPublic,
)

router = APIRouter(prefix="/documents", tags=["documents"])

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _to_public(document: Document) -> DocumentPublic:
    return DocumentPublic(
        id=document.id,
        company_id=document.company_id,
        project_id=document.project_id,
        uploaded_by=document.uploaded_by,
        file_name=document.file_name,
        file_type=document.file_type,
        file_size_bytes=document.file_size_bytes,
        document_type=document.document_type,
        status=document.status,
        checksum_sha256=document.checksum_sha256,
        processing_error_code=document.processing_error_code,
        processing_error_message=document.processing_error_message,
        indexing_status=document.indexing_status,
        indexing_error_code=document.indexing_error_code,
        indexing_error_message=document.indexing_error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.post("", response_model=DocumentPublic, status_code=201)
def upload_document(
    request: Request,
    file: UploadFile = File(...),
    project_id: uuid.UUID | None = Form(default=None),
    document_type: str = Form(...),
    # upload is owner/admin/manager -- member is read/download-only.
    context: TenantContext = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
) -> DocumentPublic:
    document = service.upload_document(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        project_id=project_id,
        document_type=document_type,
        upload_file=file,
        ip_address=get_client_ip(request),
    )
    return _to_public(document)


@router.get("", response_model=DocumentPage)
def list_documents(
    project_id: uuid.UUID | None = None,
    document_type: str | None = None,
    status: str | None = None,
    filename: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    # Read is open to every role, including member. company_id always
    # comes from the verified token via get_tenant_context.
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> DocumentPage:
    decoded_cursor = None
    if cursor is not None:
        try:
            decoded_cursor = decode_cursor(cursor)
        except InvalidCursorError:
            raise BadRequestError("Invalid pagination cursor.") from None

    # document_type is a native Postgres enum (like projects.status) --
    # an unrecognized value must be rejected before it ever reaches SQL,
    # not surfaced as an unhandled 500.
    if document_type is not None and document_type not in DOCUMENT_TYPES:
        raise BadRequestError(f"document_type must be one of {sorted(DOCUMENT_TYPES)}.")

    rows = service.list_documents(
        db,
        company_id=context.company_id,
        limit=limit + 1,  # one extra, to know whether there's a next page
        cursor=decoded_cursor,
        project_id=project_id,
        document_type=document_type,
        status=status,
        filename_search=filename,
    )

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = (
        encode_cursor(page_rows[-1].created_at, page_rows[-1].id)
        if has_more and page_rows
        else None
    )

    return DocumentPage(items=[_to_public(d) for d in page_rows], next_cursor=next_cursor)


@router.get("/{document_id}", response_model=DocumentPublic)
def get_document(
    document_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> DocumentPublic:
    document = service.get_document(db, company_id=context.company_id, document_id=document_id)
    return _to_public(document)


@router.get("/{document_id}/download", response_model=DocumentDownloadResponse)
def download_document(
    document_id: uuid.UUID,
    request: Request,
    # Read/download is open to every role, including member.
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> DocumentDownloadResponse:
    # No client-supplied object key of any kind is accepted anywhere in
    # this endpoint -- document_id resolves to a company-scoped document
    # row first, and the signed URL is generated from THAT row's own
    # storage_key, server-side only.
    url, ttl = service.get_document_download_url(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        document_id=document_id,
        ip_address=get_client_ip(request),
    )
    return DocumentDownloadResponse(download_url=url, expires_in_seconds=ttl)


@router.delete("/{document_id}", response_model=DocumentPublic)
def delete_document(
    document_id: uuid.UUID,
    request: Request,
    # delete is owner/admin only -- manager can upload/read but not
    # delete, member can only read/download. Per the approved RBAC table.
    context: TenantContext = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> DocumentPublic:
    document = service.delete_document(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        document_id=document_id,
        ip_address=get_client_ip(request),
    )
    return _to_public(document)


@router.post("/{document_id}/process", response_model=DocumentPublic)
def process_document(
    document_id: uuid.UUID,
    request: Request,
    # process is owner/admin/manager -- member is read/download-only,
    # same split as upload. Runs synchronously in this phase; no
    # background job exists yet.
    context: TenantContext = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
) -> DocumentPublic:
    document = processing_orchestrator.process_document(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        document_id=document_id,
        ip_address=get_client_ip(request),
    )
    return _to_public(document)


@router.post("/{document_id}/index", response_model=DocumentPublic)
def index_document(
    document_id: uuid.UUID,
    request: Request,
    # index is owner/admin/manager -- member is read/download-only, same
    # split as upload/process. Runs synchronously in this phase; no
    # background job exists yet.
    context: TenantContext = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
) -> DocumentPublic:
    document = indexing_orchestrator.index_document(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        document_id=document_id,
        ip_address=get_client_ip(request),
    )
    return _to_public(document)

