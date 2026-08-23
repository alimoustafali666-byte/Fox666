import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, ForeignKeyConstraint, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TASK_STATUSES: tuple[str, ...] = ("todo", "in_progress", "blocked", "completed", "cancelled")
TASK_PRIORITIES: tuple[str, ...] = ("low", "normal", "high", "urgent")
TASK_SOURCE_TYPES: tuple[str, ...] = ("manual", "document", "message", "conversation", "daily_brief", "ai_suggestion")

# Valid status transitions -- deliberately small and explicit rather than
# a workflow engine (see the Step 19 spec's "do not build a complex
# workflow engine"). Completing sets completed_at; moving off completed
# clears it. Cancelling from 'completed' is disallowed (reopen first);
# reopening a cancelled task goes back to 'todo' only.
TASK_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "todo": ("in_progress", "blocked", "cancelled"),
    "in_progress": ("todo", "blocked", "completed", "cancelled"),
    "blocked": ("todo", "in_progress", "cancelled"),
    "completed": ("todo", "in_progress"),
    "cancelled": ("todo",),
}

# Task activity event types (app-validated, not a DB enum -- see the
# migration's docstring for why). Kept as a fixed tuple so new event
# types are a code change, not silently free-form strings from anywhere.
TASK_ACTIVITY_EVENT_TYPES: tuple[str, ...] = (
    "created", "assigned", "reassigned", "status_changed", "priority_changed",
    "due_date_changed", "completed", "reopened", "commented",
)

task_status = ENUM(*TASK_STATUSES, name="task_status", create_type=False)
task_priority = ENUM(*TASK_PRIORITIES, name="task_priority", create_type=False)
task_source_type = ENUM(*TASK_SOURCE_TYPES, name="task_source_type", create_type=False)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("id", "company_id", name="uq_tasks_id_company"),
        ForeignKeyConstraint(
            ["project_id", "company_id"], ["projects.id", "projects.company_id"],
            name="fk_tasks_project_company",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    title: Mapped[str]
    description: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(task_status, server_default="todo")
    priority: Mapped[str] = mapped_column(task_priority, server_default="normal")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    source_type: Mapped[str] = mapped_column(task_source_type, server_default="manual")
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class TaskComment(Base):
    """Append-only (see migration 0018's docstring) -- no edit/delete for
    Step 19.
    """

    __tablename__ = "task_comments"
    __table_args__ = (
        # No ondelete="CASCADE" on either FK here -- see migration 0018's
        # comment on task_comments for why (a CASCADE into an
        # append-only, DELETE-revoked table fails with a confusing
        # permission error on a statement that never mentions it).
        ForeignKeyConstraint(
            ["task_id", "company_id"], ["tasks.id", "tasks.company_id"],
            name="fk_task_comments_task_company",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    author_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    body: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class TaskActivity(Base):
    """Append-only, server-written only -- never a user-facing write
    endpoint (see app.modules.tasks.service). This is the user-facing
    task history the Step 19 spec asks for, distinct from the global
    Audit Log (which also gets a parallel, security-focused entry for
    the same events -- see record_audit_event calls in service.py).
    """

    __tablename__ = "task_activity"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "company_id"], ["tasks.id", "tasks.company_id"],
            name="fk_task_activity_task_company",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    event_type: Mapped[str]
    field_name: Mapped[str | None] = mapped_column(nullable=True)
    old_value: Mapped[str | None] = mapped_column(nullable=True)
    new_value: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

