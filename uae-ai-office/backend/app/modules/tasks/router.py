"""Task Management API (Step 19). Every endpoint resolves company_id
from TenantContext, never client input. Row visibility is governed by
RLS (see migration 0018); this router additionally never widens what a
role can WRITE beyond what app.modules.tasks.service enforces --
create/update are open to all four roles at the HTTP layer because the
precise field-level and assignment rules are enforced inside service.py
(a member's own attempt to reassign someone else's task fails there with
a 403, not here), matching the pattern already used by Projects (create/
update behind require_roles) adapted for Tasks' per-row rule instead of
a single company-wide rule.
"""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError
from app.core.pagination import InvalidCursorError, decode_cursor, encode_cursor
from app.core.request_ip import get_client_ip
from app.db.session import get_db
from app.modules.auth.dependencies import get_tenant_context
from app.modules.auth.models import User
from app.modules.auth.service import TenantContext
from app.modules.projects.models import Project
from app.modules.tasks import service
from app.modules.tasks.models import TASK_PRIORITIES, TASK_STATUSES, Task, TaskActivity
from app.modules.tasks.schemas import (
    TaskActivityPublic,
    TaskCommentCreate,
    TaskCommentPublic,
    TaskCreate,
    TaskDashboardSummary,
    TaskPage,
    TaskPublic,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])

DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 100
_DUE_FILTERS = ("overdue", "due_today", "upcoming")


def _names_for(db: Session, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, str | None]:
    ids = {i for i in user_ids if i is not None}
    if not ids:
        return {}
    return {u.id: u.full_name for u in db.execute(select(User).where(User.id.in_(ids))).scalars()}


def _project_names_for(db: Session, project_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    ids = {i for i in project_ids if i is not None}
    if not ids:
        return {}
    return {p.id: p.name for p in db.execute(select(Project).where(Project.id.in_(ids))).scalars()}


def _task_to_public(task: Task, names: dict[uuid.UUID, str | None], project_names: dict[uuid.UUID, str]) -> TaskPublic:
    return TaskPublic(
        id=task.id, company_id=task.company_id, project_id=task.project_id,
        project_name=project_names.get(task.project_id) if task.project_id else None, title=task.title,
        description=task.description, status=task.status, priority=task.priority,
        assigned_to=task.assigned_to, assignee_name=names.get(task.assigned_to) if task.assigned_to else None,
        created_by=task.created_by, creator_name=names.get(task.created_by),
        source_type=task.source_type, source_id=task.source_id, due_date=task.due_date,
        completed_at=task.completed_at, created_at=task.created_at, updated_at=task.updated_at,
    )


def _tasks_to_public(db: Session, tasks: list[Task]) -> list[TaskPublic]:
    ids: set[uuid.UUID] = set()
    project_ids: set[uuid.UUID] = set()
    for t in tasks:
        ids.add(t.created_by)
        if t.assigned_to:
            ids.add(t.assigned_to)
        if t.project_id:
            project_ids.add(t.project_id)
    names = _names_for(db, ids)
    project_names = _project_names_for(db, project_ids)
    return [_task_to_public(t, names, project_names) for t in tasks]


def _decode_cursor_param(cursor: str | None):
    if cursor is None:
        return None
    try:
        return decode_cursor(cursor)
    except InvalidCursorError:
        raise BadRequestError("Invalid pagination cursor.") from None


@router.post("", response_model=TaskPublic, status_code=201)
def create_task(
    data: TaskCreate, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> TaskPublic:
    task = service.create_task(
        db, company_id=context.company_id, actor_user_id=context.user.id, actor_role=context.role,
        title=data.title, description=data.description, project_id=data.project_id, assigned_to=data.assigned_to,
        priority=data.priority, due_date=data.due_date, source_type=data.source_type, source_id=data.source_id,
        ip_address=get_client_ip(request),
    )
    return _tasks_to_public(db, [task])[0]


@router.get("", response_model=TaskPage)
def list_tasks(
    assigned_to: uuid.UUID | None = None,
    created_by: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    unscoped_only: bool = False,
    status: str | None = None,
    open_only: bool = False,
    priority: str | None = None,
    due_filter: str | None = None,
    search: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> TaskPage:
    if status is not None and status not in TASK_STATUSES:
        raise BadRequestError(f"status must be one of {sorted(TASK_STATUSES)}.")
    if priority is not None and priority not in TASK_PRIORITIES:
        raise BadRequestError(f"priority must be one of {sorted(TASK_PRIORITIES)}.")
    if due_filter is not None and due_filter not in _DUE_FILTERS:
        raise BadRequestError(f"due_filter must be one of {sorted(_DUE_FILTERS)}.")

    decoded_cursor = _decode_cursor_param(cursor)
    rows = service.list_tasks(
        db, company_id=context.company_id, limit=limit + 1, cursor=decoded_cursor,
        assigned_to=assigned_to, created_by=created_by, project_id=project_id, unscoped_only=unscoped_only,
        status=status, open_only=open_only, priority=priority, due_filter=due_filter, search=search,
    )
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = encode_cursor(page_rows[-1].created_at, page_rows[-1].id) if has_more and page_rows else None
    return TaskPage(items=_tasks_to_public(db, page_rows), next_cursor=next_cursor)


@router.get("/summary", response_model=TaskDashboardSummary)
def get_dashboard_summary(
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> TaskDashboardSummary:
    summary = service.get_dashboard_summary(db, company_id=context.company_id, actor_user_id=context.user.id)
    return TaskDashboardSummary(**summary)


@router.get("/{task_id}", response_model=TaskPublic)
def get_task(
    task_id: uuid.UUID, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> TaskPublic:
    task = service.get_task(db, company_id=context.company_id, task_id=task_id)
    return _tasks_to_public(db, [task])[0]


@router.patch("/{task_id}", response_model=TaskPublic)
def update_task(
    task_id: uuid.UUID, data: TaskUpdate, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> TaskPublic:
    changes = data.model_dump(exclude_unset=True)
    task = service.update_task(
        db, company_id=context.company_id, actor_user_id=context.user.id, actor_role=context.role,
        task_id=task_id, changes=changes, ip_address=get_client_ip(request),
    )
    return _tasks_to_public(db, [task])[0]


@router.get("/{task_id}/comments", response_model=list[TaskCommentPublic])
def list_comments(
    task_id: uuid.UUID, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> list[TaskCommentPublic]:
    comments = service.list_comments(db, company_id=context.company_id, task_id=task_id)
    names = _names_for(db, {c.author_user_id for c in comments})
    return [
        TaskCommentPublic(
            id=c.id, task_id=c.task_id, author_user_id=c.author_user_id, author_name=names.get(c.author_user_id),
            body=c.body, created_at=c.created_at,
        )
        for c in comments
    ]


@router.post("/{task_id}/comments", response_model=TaskCommentPublic, status_code=201)
def add_comment(
    task_id: uuid.UUID, data: TaskCommentCreate, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> TaskCommentPublic:
    comment = service.add_comment(
        db, company_id=context.company_id, actor_user_id=context.user.id, task_id=task_id, body=data.body,
        ip_address=get_client_ip(request),
    )
    return TaskCommentPublic(
        id=comment.id, task_id=comment.task_id, author_user_id=comment.author_user_id,
        author_name=context.user.full_name, body=comment.body, created_at=comment.created_at,
    )


@router.get("/{task_id}/activity", response_model=list[TaskActivityPublic])
def list_activity(
    task_id: uuid.UUID, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> list[TaskActivityPublic]:
    entries: list[TaskActivity] = service.list_activity(db, company_id=context.company_id, task_id=task_id)
    names = _names_for(db, {e.actor_user_id for e in entries if e.actor_user_id})
    return [
        TaskActivityPublic(
            id=e.id, task_id=e.task_id, actor_user_id=e.actor_user_id,
            actor_name=names.get(e.actor_user_id) if e.actor_user_id else None,
            event_type=e.event_type, field_name=e.field_name, old_value=e.old_value, new_value=e.new_value,
            created_at=e.created_at,
        )
        for e in entries
    ]

