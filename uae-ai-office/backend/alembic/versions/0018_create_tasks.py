"""create tasks (task management layer)

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-22

Step 19 -- Enterprise Productivity & Action Management Layer. Three new
tables (tasks, task_comments, task_activity) plus an additive extension
to Step 18's chat_notifications (new notification types + a nullable
task_id column) -- chat_notifications already carried a
support_ticket_id column and a `support_ticket_update` type that no
module used yet, confirming it was designed as the app's general
notification table, not a collaboration-only one. Extending it here
avoids building a second, parallel notification system.

VISIBILITY / RLS -- unlike documents/projects/briefs (plain company-wide
RLS, with any finer rule left entirely to the router/service layer),
`tasks` gets a genuine per-row SELECT policy, matching the elevated
rigor Step 18 established for privacy-sensitive rows. This is safe and
non-recursive: tasks references company_members (a distinct table with
no policy that references tasks back), so there is no cycle -- nothing
like the join-table indirection Step 18's conversations needed.

Policy: a task is visible if
  - it belongs to a project (project-scoped tasks are company-wide
    visible, exactly matching Projects' own existing visibility -- this
    app has no separate "project membership" concept, so "authorized for
    the project" already means "any company member"), OR
  - the caller created it, OR
  - the caller is its assignee, OR
  - the caller's company_role is owner/admin/manager (management roles
    see everything, per the approved RBAC table).

UPDATE mirrors SELECT at the RLS layer (the outer, fail-closed
boundary); the service layer enforces the precise field-level rule
("a member may only change the status of a task assigned to them") on
top -- RLS decides *whether a row is reachable at all*, never the exact
business permission for a given field, same division of responsibility
used throughout this app (e.g. Projects' RLS is company-wide, but only
owner/admin/manager may actually call the create/update endpoints).

No DELETE policy on tasks: "delete" is status='cancelled' via UPDATE,
mirroring app.modules.projects.service.delete_project's own established
"delete means archive" precedent. No soft-delete column is needed for
the same reason projects.py has none.

task_comments and task_activity are both append-only (no UPDATE/DELETE
policy at all, matching audit_logs' precedent from migration 0009) and
both gate SELECT/INSERT through an EXISTS against `tasks` -- a one-way
reference (tasks has no policy referencing either of these tables back),
so this is a clean DAG, not a repeat of Step 18's recursion problem.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COMPANY_EXPR = "company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid"
_USER_EXPR = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"

_TASK_STATUSES = ("todo", "in_progress", "blocked", "completed", "cancelled")
_TASK_PRIORITIES = ("low", "normal", "high", "urgent")
_TASK_SOURCE_TYPES = ("manual", "document", "message", "conversation", "daily_brief", "ai_suggestion")

# Additive: three new values for Step 18's collaboration_notification_type
# enum. Deliberately NOT adding task_due_soon/task_overdue -- there is no
# scheduler/background worker anywhere in this app (documents processing
# and brief generation are both synchronous on-request), so a "due soon"
# push notification would never actually fire; due/overdue surfacing is
# computed on read instead (see app.modules.tasks.repository). Including
# unreachable enum values here would misrepresent that as implemented.
_NEW_NOTIFICATION_TYPES = ("task_assigned", "task_reassigned", "task_comment")

_CURRENT_COMPANY_ID = "NULLIF(current_setting('app.current_company_id', true), '')::uuid"

_MANAGEMENT_ROLES_EXPR = (
    f"EXISTS (SELECT 1 FROM company_members cm WHERE cm.company_id = {_CURRENT_COMPANY_ID} "
    f"AND cm.user_id = {_USER_EXPR} AND cm.role IN ('owner', 'admin', 'manager'))"
)

_TASK_VISIBILITY_EXPR = (
    f"({_COMPANY_EXPR} AND (project_id IS NOT NULL OR created_by = {_USER_EXPR} "
    f"OR assigned_to = {_USER_EXPR} OR {_MANAGEMENT_ROLES_EXPR}))"
)

_TASK_EXISTS_EXPR = (
    f"EXISTS (SELECT 1 FROM tasks t WHERE t.id = task_id AND t.company_id = {_CURRENT_COMPANY_ID})"
)


def upgrade() -> None:
    def enum(name: str, values: tuple[str, ...]) -> None:
        values_sql = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {name} AS ENUM ({values_sql})")

    enum("task_status", _TASK_STATUSES)
    enum("task_priority", _TASK_PRIORITIES)
    enum("task_source_type", _TASK_SOURCE_TYPES)

    for value in _NEW_NOTIFICATION_TYPES:
        # IF NOT EXISTS makes this safe to re-run against a database that
        # already has the value (e.g. a downgrade-then-upgrade cycle
        # during local development -- Postgres has no ALTER TYPE ... DROP
        # VALUE, so downgrade() cannot actually remove these; see its
        # note below).
        op.execute(f"ALTER TYPE collaboration_notification_type ADD VALUE IF NOT EXISTS '{value}'")

    # --- tasks ---
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        # No direct ForeignKey() -- the composite constraint below ties it
        # to company_id too, same pattern as documents.project_id.
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", postgresql.ENUM(name="task_status", create_type=False), nullable=False, server_default="todo"),
        sa.Column("priority", postgresql.ENUM(name="task_priority", create_type=False), nullable=False, server_default="normal"),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        # source_type always has a value ('manual' for the plain creation
        # form); source_id stays nullable (NULL for manual/unspecified).
        # No FK on source_id: it points at a different table depending on
        # source_type, so referential integrity is enforced at the
        # application layer at creation time instead (re-validated against
        # the real owning module, same discipline Step 18 uses for
        # shared_document_id) -- see the module docstring in
        # app.modules.tasks.service for why a blind DB FK isn't the right
        # tool here.
        sa.Column("source_type", postgresql.ENUM(name="task_source_type", create_type=False), nullable=False, server_default="manual"),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("id", "company_id", name="uq_tasks_id_company"),
        sa.ForeignKeyConstraint(
            ["project_id", "company_id"], ["projects.id", "projects.company_id"],
            name="fk_tasks_project_company",
        ),
    )
    op.create_index("ix_tasks_company_id", "tasks", ["company_id", "created_at"])
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])
    op.create_index("ix_tasks_assigned_to", "tasks", ["assigned_to"])
    op.create_index("ix_tasks_created_by", "tasks", ["created_by"])
    op.create_index("ix_tasks_due_date", "tasks", ["due_date"])

    op.execute("ALTER TABLE tasks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tasks FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_visibility_select ON tasks FOR SELECT USING ({_TASK_VISIBILITY_EXPR})")
    op.execute(
        f"CREATE POLICY tenant_visibility_insert ON tasks FOR INSERT "
        f"WITH CHECK ({_COMPANY_EXPR} AND created_by = {_USER_EXPR})"
    )
    op.execute(
        f"CREATE POLICY tenant_visibility_update ON tasks FOR UPDATE "
        f"USING ({_TASK_VISIBILITY_EXPR}) WITH CHECK ({_TASK_VISIBILITY_EXPR})"
    )

    # --- task_comments (append-only) ---
    # Neither FK below uses ondelete="CASCADE" -- migration 0009 discovered
    # (for audit_logs) that Postgres enforces a FK's CASCADE action using
    # the REFERENCING table's own grants, not the deleting statement's;
    # since UPDATE/DELETE/TRUNCATE are revoked from uae_app on this table
    # below, a CASCADE into it (from deleting a company, or a task) would
    # fail with a confusing "permission denied for table task_comments"
    # on a statement that never mentions this table at all. Neither
    # companies nor tasks are ever hard-deleted by this app in practice
    # (tasks use status='cancelled'; there is no company-delete feature),
    # so this is a safe, inert constraint, not a behavior change.
    op.create_table(
        "task_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["task_id", "company_id"], ["tasks.id", "tasks.company_id"],
            name="fk_task_comments_task_company",
        ),
    )
    op.create_index("ix_task_comments_task_id", "task_comments", ["task_id", "created_at"])

    op.execute("ALTER TABLE task_comments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE task_comments FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_visibility_select ON task_comments FOR SELECT USING ({_COMPANY_EXPR} AND {_TASK_EXISTS_EXPR})")
    op.execute(
        f"CREATE POLICY tenant_visibility_insert ON task_comments FOR INSERT "
        f"WITH CHECK ({_COMPANY_EXPR} AND author_user_id = {_USER_EXPR} AND {_TASK_EXISTS_EXPR})"
    )
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON task_comments FROM uae_app")

    # --- task_activity (append-only) ---
    op.create_table(
        "task_activity",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        # Free text (like documents.status / audit_logs.action), not a DB
        # enum -- validated against a fixed tuple at the service layer.
        # New event types can be added without a migration.
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("field_name", sa.Text(), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["task_id", "company_id"], ["tasks.id", "tasks.company_id"],
            name="fk_task_activity_task_company",
        ),
    )
    op.create_index("ix_task_activity_task_id", "task_activity", ["task_id", "created_at"])

    op.execute("ALTER TABLE task_activity ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE task_activity FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_visibility_select ON task_activity FOR SELECT USING ({_COMPANY_EXPR} AND {_TASK_EXISTS_EXPR})")
    op.execute(f"CREATE POLICY tenant_visibility_insert ON task_activity FOR INSERT WITH CHECK ({_COMPANY_EXPR} AND {_TASK_EXISTS_EXPR})")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON task_activity FROM uae_app")

    # --- chat_notifications extension ---
    op.add_column("chat_notifications", sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_notifications", "task_id")

    op.execute("GRANT UPDATE, DELETE, TRUNCATE ON task_activity TO uae_app")
    op.drop_table("task_activity")

    op.execute("GRANT UPDATE, DELETE, TRUNCATE ON task_comments TO uae_app")
    op.drop_table("task_comments")

    op.drop_table("tasks")

    op.execute("DROP TYPE task_source_type")
    op.execute("DROP TYPE task_priority")
    op.execute("DROP TYPE task_status")

    # Note: the three new collaboration_notification_type values are NOT
    # removed here -- Postgres has no ALTER TYPE ... DROP VALUE, and this
    # mirrors migration 0017's own downgrade() note about enum values
    # being append-only once added. A full downgrade of this enum would
    # require recreating the type from scratch and repointing every
    # column that uses it, which is out of scope for a routine downgrade.

