import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError
from app.core.pagination import InvalidCursorError, decode_cursor, encode_cursor
from app.core.request_ip import get_client_ip
from app.db.session import get_db
from app.modules.auth.dependencies import get_tenant_context, require_roles
from app.modules.auth.service import TenantContext
from app.modules.projects import service
from app.modules.projects.models import PROJECT_STATUSES, Project
from app.modules.projects.schemas import ProjectCreate, ProjectPage, ProjectPublic, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _to_public(project: Project) -> ProjectPublic:
    return ProjectPublic(
        id=project.id,
        company_id=project.company_id,
        name=project.name,
        project_code=project.project_code,
        description=project.description,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.post("", response_model=ProjectPublic, status_code=201)
def create_project(
    data: ProjectCreate,
    request: Request,
    # create is owner/admin/manager -- member is read-only.
    context: TenantContext = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
) -> ProjectPublic:
    project = service.create_project(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        data=data,
        ip_address=get_client_ip(request),
    )
    return _to_public(project)


@router.get("", response_model=ProjectPage)
def list_projects(
    status: str | None = None,
    project_code: str | None = None,
    name: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    # Read is open to every role (including member). company_id always
    # comes from the verified token via get_tenant_context -- there is no
    # query/body/path parameter a client could use to select another
    # tenant's projects.
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> ProjectPage:
    decoded_cursor = None
    if cursor is not None:
        try:
            decoded_cursor = decode_cursor(cursor)
        except InvalidCursorError:
            raise BadRequestError("Invalid pagination cursor.") from None

    # Unlike audit_logs.action/resource_type (plain TEXT, so an unknown
    # filter value just matches nothing), projects.status is a native
    # Postgres enum -- an invalid value isn't a "no rows match" case, the
    # database itself rejects the query outright. Validate before it ever
    # reaches SQL rather than let that surface as an unhandled 500.
    if status is not None and status not in PROJECT_STATUSES:
        raise BadRequestError(f"status must be one of {sorted(PROJECT_STATUSES)}.")

    rows = service.list_projects(
        db,
        company_id=context.company_id,
        limit=limit + 1,  # one extra, to know whether there's a next page
        cursor=decoded_cursor,
        status=status,
        project_code=project_code,
        name_search=name,
    )

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = (
        encode_cursor(page_rows[-1].created_at, page_rows[-1].id)
        if has_more and page_rows
        else None
    )

    return ProjectPage(items=[_to_public(p) for p in page_rows], next_cursor=next_cursor)


@router.get("/{project_id}", response_model=ProjectPublic)
def get_project(
    project_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> ProjectPublic:
    project = service.get_project(db, company_id=context.company_id, project_id=project_id)
    return _to_public(project)


@router.patch("/{project_id}", response_model=ProjectPublic)
def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    request: Request,
    context: TenantContext = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
) -> ProjectPublic:
    project = service.update_project(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        project_id=project_id,
        data=data,
        ip_address=get_client_ip(request),
    )
    return _to_public(project)


@router.delete("/{project_id}", response_model=ProjectPublic)
def delete_project(
    project_id: uuid.UUID,
    request: Request,
    # cancel/archive is owner/admin only -- manager can create/update but
    # not delete, per the approved RBAC table.
    context: TenantContext = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> ProjectPublic:
    project = service.delete_project(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        project_id=project_id,
        ip_address=get_client_ip(request),
    )
    return _to_public(project)

