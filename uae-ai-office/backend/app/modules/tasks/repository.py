import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.modules.tasks.models import Task, TaskActivity, TaskComment

# Applied identically by list_tasks and count_tasks so "how many overdue
# tasks" (Dashboard tiles) and "show me the overdue tasks" (My Tasks
# filter) always agree. A completed/cancelled task is never "overdue" or
# "due today" even if its due_date has passed -- the whole point of
# these filters is outstanding work, not historical record-keeping.
_OPEN_STATUSES = ("todo", "in_progress", "blocked")


def _apply_filters(
    query,
    *,
    company_id: uuid.UUID,
    assigned_to: uuid.UUID | None,
    created_by: uuid.UUID | None,
    project_id: uuid.UUID | None,
    unscoped_only: bool,
    status: str | None,
    open_only: bool,
    priority: str | None,
    due_filter: str | None,
    search: str | None,
    today: date,
):
    query = query.where(Task.company_id == company_id)
    if assigned_to is not None:
        query = query.where(Task.assigned_to == assigned_to)
    if created_by is not None:
        query = query.where(Task.created_by == created_by)
    if project_id is not None:
        query = query.where(Task.project_id == project_id)
    if unscoped_only:
        query = query.where(Task.project_id.is_(None))
    if status is not None:
        query = query.where(Task.status == status)
    elif open_only:
        query = query.where(Task.status.in_(_OPEN_STATUSES))
    if priority is not None:
        query = query.where(Task.priority == priority)
    if due_filter == "overdue":
        query = query.where(Task.due_date < today, Task.status.in_(_OPEN_STATUSES))
    elif due_filter == "due_today":
        query = query.where(Task.due_date == today, Task.status.in_(_OPEN_STATUSES))
    elif due_filter == "upcoming":
        query = query.where(Task.due_date > today, Task.status.in_(_OPEN_STATUSES))
    if search is not None:
        pattern = f"%{search}%"
        query = query.where(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))
    return query


def create_task(
    db: Session,
    *,
    id: uuid.UUID,
    company_id: uuid.UUID,
    project_id: uuid.UUID | None,
    title: str,
    description: str | None,
    status: str,
    priority: str,
    assigned_to: uuid.UUID | None,
    created_by: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID | None,
    due_date: date | None,
) -> Task:
    task = Task(
        id=id, company_id=company_id, project_id=project_id, title=title, description=description,
        status=status, priority=priority, assigned_to=assigned_to, created_by=created_by,
        source_type=source_type, source_id=source_id, due_date=due_date,
    )
    db.add(task)
    db.flush()
    return task


def get_task_by_id(db: Session, *, company_id: uuid.UUID, task_id: uuid.UUID) -> Task | None:
    """RLS's own visibility policy already filters this to rows the
    caller may see (own/assigned/project-scoped/management role) -- the
    explicit company_id here is defense in depth, matching every other
    module's get_by_id convention, not a substitute for it.
    """
    return db.execute(select(Task).where(Task.id == task_id, Task.company_id == company_id)).scalar_one_or_none()


def list_tasks(
    db: Session,
    *,
    company_id: uuid.UUID,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None,
    assigned_to: uuid.UUID | None = None,
    created_by: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    unscoped_only: bool = False,
    status: str | None = None,
    open_only: bool = False,
    priority: str | None = None,
    due_filter: str | None = None,
    search: str | None = None,
    today: date | None = None,
) -> list[Task]:
    query = _apply_filters(
        select(Task), company_id=company_id, assigned_to=assigned_to, created_by=created_by,
        project_id=project_id, unscoped_only=unscoped_only, status=status, open_only=open_only, priority=priority,
        due_filter=due_filter, search=search, today=today or datetime.now(UTC).date(),
    )
    if cursor is not None:
        cursor_created_at, cursor_id = cursor
        query = query.where(
            or_(Task.created_at < cursor_created_at, and_(Task.created_at == cursor_created_at, Task.id < cursor_id))
        )
    query = query.order_by(Task.created_at.desc(), Task.id.desc()).limit(limit)
    return list(db.execute(query).scalars())


def count_tasks(
    db: Session,
    *,
    company_id: uuid.UUID,
    assigned_to: uuid.UUID | None = None,
    created_by: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    unscoped_only: bool = False,
    status: str | None = None,
    open_only: bool = False,
    priority: str | None = None,
    due_filter: str | None = None,
    search: str | None = None,
    today: date | None = None,
) -> int:
    query = _apply_filters(
        select(func.count(Task.id)), company_id=company_id, assigned_to=assigned_to, created_by=created_by,
        project_id=project_id, unscoped_only=unscoped_only, status=status, open_only=open_only, priority=priority,
        due_filter=due_filter, search=search, today=today or datetime.now(UTC).date(),
    )
    return db.execute(query).scalar_one()


def update_task(db: Session, task: Task, changes: dict[str, Any]) -> Task:
    for field, value in changes.items():
        setattr(task, field, value)
    task.updated_at = datetime.now(UTC)
    db.flush()
    return task


def list_comments(db: Session, *, company_id: uuid.UUID, task_id: uuid.UUID) -> list[TaskComment]:
    return list(
        db.execute(
            select(TaskComment)
            .where(TaskComment.company_id == company_id, TaskComment.task_id == task_id)
            .order_by(TaskComment.created_at.asc())
        ).scalars()
    )


def create_comment(db: Session, *, id: uuid.UUID, company_id: uuid.UUID, task_id: uuid.UUID, author_user_id: uuid.UUID, body: str) -> TaskComment:
    comment = TaskComment(id=id, company_id=company_id, task_id=task_id, author_user_id=author_user_id, body=body)
    db.add(comment)
    db.flush()
    return comment


def list_activity(db: Session, *, company_id: uuid.UUID, task_id: uuid.UUID) -> list[TaskActivity]:
    return list(
        db.execute(
            select(TaskActivity)
            .where(TaskActivity.company_id == company_id, TaskActivity.task_id == task_id)
            .order_by(TaskActivity.created_at.desc())
        ).scalars()
    )


def create_activity(
    db: Session,
    *,
    id: uuid.UUID,
    company_id: uuid.UUID,
    task_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    event_type: str,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
) -> TaskActivity:
    activity = TaskActivity(
        id=id, company_id=company_id, task_id=task_id, actor_user_id=actor_user_id, event_type=event_type,
        field_name=field_name, old_value=old_value, new_value=new_value,
    )
    db.add(activity)
    db.flush()
    return activity

