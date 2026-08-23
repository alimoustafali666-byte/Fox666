"""Task business logic (Step 19). Mirrors the layering used throughout
this app: router resolves TenantContext -> service enforces RBAC/
visibility/business rules -> repository does plain data access. RLS is
the fail-closed outer boundary (see migration 0018); everything here is
defense-in-depth ON TOP of it, and the two must never diverge on "can
this row be reached at all" -- only on "which specific fields, exactly,
may this specific role change".

RBAC (approved policy):
  owner/admin/manager: full task CRUD within the company, may assign any
    company member.
  member: may create a task assigned to themselves or unassigned; may
    fully edit a task they created; on a task assigned to them but
    created by someone else, may change status only ("update their own
    assigned task progress" -- never reassign, retitle, or reprioritize
    someone else's task). A task only reachable via the project-scoped
    company-wide visibility rule (neither creator nor assignee) is
    read-only for a member.

SOURCE REFERENCES: source_type/source_id are never a blind pointer.
_validate_source_reference re-checks the reference against the OWNING
module's own authorization at creation time only (the same discipline
Step 18 uses for shared_document_id) -- a task's title/description are
independent, user-provided text the creator already had legitimate
access to write; the source_id is never used to pull additional content
server-side. A later viewer following the "view source" link re-runs
that module's own independent authorization check (e.g. GET
/collaboration/conversations/{id}/messages) -- a stale/foreign source_id
never grants access, it just makes that follow-up call fail exactly as
it would if the viewer navigated there directly.

NOTIFICATIONS reuse Step 18's chat_notifications table (see migration
0018's docstring for why) via collaboration.repository.create_notification
directly -- notification READ authorization is therefore already
strictly recipient-private via that table's own existing RLS policy,
unchanged by this module.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.modules.audit_log.service import record_audit_event
from app.modules.auth import repository as auth_repository
from app.modules.briefs import repository as briefs_repository
from app.modules.collaboration import repository as collaboration_repository
from app.modules.collaboration import service as collaboration_service
from app.modules.documents import service as documents_service
from app.modules.projects import service as projects_service
from app.modules.tasks import repository
from app.modules.tasks.exceptions import (
    InvalidAssigneeError,
    InvalidSourceReferenceError,
    InvalidTaskStatusTransitionError,
    NotTaskAuthorizedError,
    TaskNotFoundError,
)
from app.modules.tasks.models import TASK_STATUS_TRANSITIONS, Task, TaskComment

_MANAGEMENT_ROLES = ("owner", "admin", "manager")
_ALL_EDITABLE_FIELDS = frozenset({"title", "description", "status", "priority", "assigned_to", "project_id", "due_date"})
_AUDIT_SAFE_FIELDS = {"status", "priority", "assigned_to", "project_id", "due_date"}


def _require_task(db: Session, *, company_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    task = repository.get_task_by_id(db, company_id=company_id, task_id=task_id)
    if task is None:
        raise TaskNotFoundError("Task not found.")
    return task


def _validate_assignee(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, actor_role: str, assigned_to: uuid.UUID | None) -> None:
    if assigned_to is None or assigned_to == actor_user_id:
        return
    if actor_role not in _MANAGEMENT_ROLES:
        raise InvalidAssigneeError("You can only assign tasks to yourself.")
    if auth_repository.get_membership(db, assigned_to, company_id) is None:
        raise InvalidAssigneeError("The requested assignee is not a member of your company.")


def _validate_source_reference(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, source_type: str, source_id: uuid.UUID | None) -> None:
    if source_type == "manual" or source_id is None:
        return
    try:
        if source_type == "document":
            documents_service.get_document(db, company_id=company_id, document_id=source_id)
        elif source_type in ("message", "ai_suggestion"):
            collaboration_service.get_message_for_reference(db, company_id=company_id, actor_user_id=actor_user_id, message_id=source_id)
        elif source_type == "conversation":
            collaboration_service.get_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=source_id)
        elif source_type == "daily_brief":
            item = briefs_repository.get_brief_item_by_id(db, company_id=company_id, item_id=source_id)
            if item is None:
                raise InvalidSourceReferenceError("Referenced brief item not found.")
    except InvalidSourceReferenceError:
        raise
    except Exception:  # noqa: BLE001 -- any of the above modules' own 404/403 becomes one generic, IDOR-safe error
        raise InvalidSourceReferenceError("The referenced source could not be found or is not accessible to you.") from None


def _field_permissions(task: Task, *, actor_user_id: uuid.UUID, actor_role: str) -> frozenset[str]:
    if actor_role in _MANAGEMENT_ROLES:
        return _ALL_EDITABLE_FIELDS
    if task.created_by == actor_user_id:
        return _ALL_EDITABLE_FIELDS
    if task.assigned_to == actor_user_id:
        return frozenset({"status"})
    return frozenset()


def create_task(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: str,
    title: str,
    description: str | None,
    project_id: uuid.UUID | None,
    assigned_to: uuid.UUID | None,
    priority: str,
    due_date: date | None,
    source_type: str,
    source_id: uuid.UUID | None,
    ip_address: str | None,
) -> Task:
    if project_id is not None:
        projects_service.get_project(db, company_id=company_id, project_id=project_id)
    _validate_assignee(db, company_id=company_id, actor_user_id=actor_user_id, actor_role=actor_role, assigned_to=assigned_to)
    _validate_source_reference(db, company_id=company_id, actor_user_id=actor_user_id, source_type=source_type, source_id=source_id)

    task_id = uuid.uuid4()
    task = repository.create_task(
        db, id=task_id, company_id=company_id, project_id=project_id, title=title.strip(), description=description,
        status="todo", priority=priority, assigned_to=assigned_to, created_by=actor_user_id,
        source_type=source_type, source_id=source_id, due_date=due_date,
    )
    repository.create_activity(
        db, id=uuid.uuid4(), company_id=company_id, task_id=task.id, actor_user_id=actor_user_id, event_type="created",
    )
    if assigned_to is not None and assigned_to != actor_user_id:
        repository.create_activity(
            db, id=uuid.uuid4(), company_id=company_id, task_id=task.id, actor_user_id=actor_user_id,
            event_type="assigned", field_name="assigned_to", new_value=str(assigned_to),
        )
        collaboration_repository.create_notification(
            db, id=uuid.uuid4(), company_id=company_id, user_id=assigned_to, type="task_assigned",
            conversation_id=None, message_id=None, support_ticket_id=None, task_id=task.id,
            title="You were assigned a task", body=task.title[:200],
        )

    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="task.created", resource_type="task",
        resource_id=task.id,
        metadata={"title": task.title, "status": task.status, "priority": task.priority, "project_id": str(project_id) if project_id else None, "assigned_to": str(assigned_to) if assigned_to else None},
        ip_address=ip_address,
    )
    db.commit()
    return task


def get_task(db: Session, *, company_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    return _require_task(db, company_id=company_id, task_id=task_id)


def list_tasks(db: Session, *, company_id: uuid.UUID, **filters) -> list[Task]:
    return repository.list_tasks(db, company_id=company_id, **filters)


def get_dashboard_summary(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID) -> dict[str, int]:
    """Scoped to the acting user's own tasks -- a personal dashboard
    summary, not a company-wide management metric (Team Tasks is the
    surface for that). Every count uses real, already-queryable task
    data; nothing here is a fabricated KPI.
    """
    today = datetime.now(UTC).date()
    base = {"db": db, "company_id": company_id, "assigned_to": actor_user_id, "today": today}
    return {
        "my_open_tasks": repository.count_tasks(open_only=True, **base),
        "due_today": repository.count_tasks(due_filter="due_today", **base),
        "overdue": repository.count_tasks(due_filter="overdue", **base),
        "high_priority_open": (
            repository.count_tasks(open_only=True, priority="high", **base)
            + repository.count_tasks(open_only=True, priority="urgent", **base)
        ),
    }


def update_task(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: str,
    task_id: uuid.UUID,
    changes: dict,
    ip_address: str | None,
) -> Task:
    task = _require_task(db, company_id=company_id, task_id=task_id)
    if not changes:
        return task

    allowed = _field_permissions(task, actor_user_id=actor_user_id, actor_role=actor_role)
    disallowed = set(changes) - allowed
    if disallowed:
        raise NotTaskAuthorizedError(f"You are not authorized to change: {', '.join(sorted(disallowed))}.")

    if "status" in changes and changes["status"] != task.status:
        allowed_next = TASK_STATUS_TRANSITIONS.get(task.status, ())
        if changes["status"] not in allowed_next:
            raise InvalidTaskStatusTransitionError(f"Cannot move a task from '{task.status}' to '{changes['status']}'.")

    if "project_id" in changes and changes["project_id"] is not None:
        projects_service.get_project(db, company_id=company_id, project_id=changes["project_id"])

    previous_assignee = task.assigned_to
    if "assigned_to" in changes:
        _validate_assignee(db, company_id=company_id, actor_user_id=actor_user_id, actor_role=actor_role, assigned_to=changes["assigned_to"])

    activity_entries: list[dict] = []
    for field in ("title", "description", "priority", "project_id", "due_date", "assigned_to"):
        if field in changes and changes[field] != getattr(task, field):
            activity_entries.append({
                "event_type": "reassigned" if field == "assigned_to" and task.assigned_to is not None else
                              "assigned" if field == "assigned_to" else f"{field}_changed",
                "field_name": field,
                "old_value": str(getattr(task, field)) if getattr(task, field) is not None else None,
                "new_value": str(changes[field]) if changes[field] is not None else None,
            })

    if "status" in changes and changes["status"] != task.status:
        if changes["status"] == "completed":
            changes["completed_at"] = datetime.now(UTC)
            activity_entries.append({"event_type": "completed", "field_name": "status", "old_value": task.status, "new_value": "completed"})
        elif task.status == "completed":
            changes["completed_at"] = None
            activity_entries.append({"event_type": "reopened", "field_name": "status", "old_value": task.status, "new_value": changes["status"]})
        else:
            activity_entries.append({"event_type": "status_changed", "field_name": "status", "old_value": task.status, "new_value": changes["status"]})

    repository.update_task(db, task, changes)

    for entry in activity_entries:
        repository.create_activity(db, id=uuid.uuid4(), company_id=company_id, task_id=task.id, actor_user_id=actor_user_id, **entry)

    if "assigned_to" in changes:
        new_assignee = changes["assigned_to"]
        if new_assignee is not None and new_assignee != actor_user_id and new_assignee != previous_assignee:
            notif_type = "task_assigned" if previous_assignee is None else "task_reassigned"
            title = "You were assigned a task" if previous_assignee is None else "A task was reassigned to you"
            collaboration_repository.create_notification(
                db, id=uuid.uuid4(), company_id=company_id, user_id=new_assignee, type=notif_type,
                conversation_id=None, message_id=None, support_ticket_id=None, task_id=task.id,
                title=title, body=task.title[:200],
            )

    changed_audit_fields = sorted(f for f in changes if f in _AUDIT_SAFE_FIELDS or f == "completed_at")
    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id,
        action="task.completed" if changes.get("status") == "completed" else "task.updated",
        resource_type="task", resource_id=task.id,
        metadata={"changed_fields": changed_audit_fields, "status": task.status},
        ip_address=ip_address,
    )
    db.commit()
    return task


def add_comment(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, task_id: uuid.UUID, body: str, ip_address: str | None) -> TaskComment:
    task = _require_task(db, company_id=company_id, task_id=task_id)
    comment = repository.create_comment(db, id=uuid.uuid4(), company_id=company_id, task_id=task.id, author_user_id=actor_user_id, body=body.strip())
    repository.create_activity(db, id=uuid.uuid4(), company_id=company_id, task_id=task.id, actor_user_id=actor_user_id, event_type="commented")

    notify_targets = {uid for uid in (task.assigned_to, task.created_by) if uid is not None and uid != actor_user_id}
    for target in notify_targets:
        collaboration_repository.create_notification(
            db, id=uuid.uuid4(), company_id=company_id, user_id=target, type="task_comment",
            conversation_id=None, message_id=None, support_ticket_id=None, task_id=task.id,
            title="New comment on a task", body=comment.body[:200],
        )

    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="task.comment_added", resource_type="task",
        resource_id=task.id, metadata={"comment_id": str(comment.id)}, ip_address=ip_address,
    )
    db.commit()
    return comment


def list_comments(db: Session, *, company_id: uuid.UUID, task_id: uuid.UUID) -> list[TaskComment]:
    _require_task(db, company_id=company_id, task_id=task_id)
    return repository.list_comments(db, company_id=company_id, task_id=task_id)


def list_activity(db: Session, *, company_id: uuid.UUID, task_id: uuid.UUID):
    _require_task(db, company_id=company_id, task_id=task_id)
    return repository.list_activity(db, company_id=company_id, task_id=task_id)

