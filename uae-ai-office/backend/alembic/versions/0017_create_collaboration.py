"""create collaboration schema (chat_conversations, chat_messages, calls, notifications)

Step 18 -- Company Communication & AI Collaboration. Nine new tenant-owned
tables, all prefixed `chat_` -- Step 11 already claimed the bare
`conversations`/`messages` table names for Ask Your Business, a
deliberately distinct concept (a private Q&A thread with an AI, never
company chat). The `chat_` prefix keeps the two permanently
unambiguous in the schema, not just in application code.

RLS throughout follows the same two patterns already established by
conversations/messages (Step 11) and support_tickets (Step 17), but
generalized from "creator-private" to "any active conversation member".
Getting this right took two failed designs and real, empirically-verified
Postgres constraints -- documented in full because the final shape (a
dedicated chat_conversation_active_members join table, see below) looks
like unnecessary indirection unless you know why the two simpler designs
are impossible here.

  _COMPANY_EXPR: company_id must match app.current_company_id (every
  table).

  Design attempt 1 -- self-referencing EXISTS on chat_conversation_members
  itself (including its own policy, self-joining its own table): REJECTED.
  Verified directly against this project's database: Postgres raises
  "infinite recursion detected in policy for relation
  chat_conversation_members". This is a structural/plan-time check across
  a table's *entire* policy set, not a runtime short-circuit -- adding a
  second, non-recursive OR'd policy on the same table does not help
  (verified: a minimal two-policy repro on a scratch table still raised
  the same error). The standard fix for this shape of problem -- a
  SECURITY DEFINER function owned by a BYPASSRLS role -- is not available
  here: this project's app DB role (uae_app, the same role Alembic itself
  connects as) has rolsuper=false, rolcreaterole=false, rolbypassrls=false
  (confirmed via pg_roles), cannot grant itself BYPASSRLS, and no
  superuser role is reachable from this environment to grant it either
  (confirmed by connection attempts). `SET LOCAL row_security = off` was
  also confirmed (via a direct psql test) not to help while FORCE ROW
  LEVEL SECURITY is set -- and FORCE must stay, since the app connects as
  the same owner role and relies on FORCE to be constrained by RLS at all.

  Design attempt 2 -- denormalize an active_member_ids uuid[] column onto
  chat_conversations itself, with chat_conversations' own policy doing a
  direct `current_user = ANY(active_member_ids)` check (no subquery, so
  it can't recurse) and every other table (including
  chat_conversation_members) checking membership via an EXISTS against
  THAT column instead of against chat_conversation_members: REJECTED,
  also verified empirically. This breaks the recursion, but hits a
  second, independent Postgres RLS rule: for UPDATE, Postgres requires
  the POST-image of the row to still satisfy the table's SELECT policy,
  in addition to the UPDATE policy's own WITH CHECK -- confirmed with a
  minimal repro where WITH CHECK (true) was explicitly set and the UPDATE
  *still* failed once a stricter SELECT policy existed, and confirmed
  again with `SET LOCAL row_security = off` under FORCE (still blocked).
  Practically: a member removing themselves from active_member_ids is
  exactly an UPDATE whose post-image excludes the acting user under a
  membership-based SELECT policy -- so leaving a conversation would
  always fail, and the case this system's own spec requires ("last member
  leaves -> conversation archived, membership becomes empty") is provably
  impossible under this shape: no current_user value can ever satisfy
  `x = ANY('{}')`, so literally nobody's session could perform that write.

  Final design -- a dedicated chat_conversation_active_members join table,
  used ONLY as an internal RLS-plumbing table (never queried directly by
  the application) whose own SELECT policy is a *direct, non-subquery*
  own-row check (`user_id = current_user`). That single non-recursive
  policy is enough to answer "is current_user active in conversation X"
  everywhere it's needed, because that question only ever needs to find
  the CURRENT user's own row -- never a peer's. Concretely:
    - chat_conversation_active_members: SELECT policy is direct
      (`user_id = current_user`, no subquery -- the terminal node).
      INSERT/DELETE policies allow either your own row, or any row, via
      `EXISTS (SELECT ... FROM chat_conversation_active_members existing
      WHERE existing.conversation_id = ... AND existing.user_id =
      current_user)` -- a self-referencing EXISTS, but one that is safe:
      the inner SELECT it triggers is governed by the direct, non-
      recursive SELECT policy above, not by the INSERT/DELETE policy
      being evaluated, so there is no fixed point (verified empirically
      with a minimal repro covering self-insert, peer-insert-by-existing-
      member, self-delete, and delete-down-to-zero-members).
    - chat_conversations, chat_conversation_members, and every other
      table below reference chat_conversation_active_members via
      _member_exists_expr() (an EXISTS filtered by that table's direct
      SELECT policy) -- never each other, never themselves. The
      dependency graph is a clean DAG with chat_conversation_active_members
      as the one terminal, self-contained node.
    - Leaving is therefore DELETE (from chat_conversation_active_members),
      not UPDATE -- and DELETE has no WITH-CHECK/post-image requirement
      in Postgres RLS, so a member removing their own row (even the last
      remaining row for a conversation) always succeeds. The ordering
      that makes a full "leave" safe: (1) UPDATE
      chat_conversation_members.removed_at for your own row (still passes
      -- your active_members row hasn't been touched yet), (2) if you are
      the last active member, UPDATE chat_conversations.archived_at
      (same reason), (3) DELETE your row from
      chat_conversation_active_members last. After step 3 a fully-vacated
      conversation becomes invisible to everyone via the live,
      membership-gated read path -- a deliberate, documented
      simplification; recovering an archived conversation's history is an
      operational/audit concern out of scope for this step, not a live
      API path.

Table summary:

- chat_conversations: direct / group / project_channel. project_id is a
  composite FK to projects(id, company_id) (NULL unless type =
  project_channel), so a channel can never reference another company's
  project. archived_at is set when the last active member leaves (see
  the RLS discussion above) or on an explicit archive action.
- chat_conversation_active_members: the RLS-plumbing table described
  above. One row per (conversation, currently-active user) -- no other
  columns, no history (that's what chat_conversation_members.removed_at
  is for). Never queried directly by the application; exists purely so
  every other table's membership gate has a non-recursive, terminal
  table to check.
- chat_conversation_members: conversation-level role (owner/admin/member)
  -- DELIBERATELY a separate enum from company_role (Step 1), never
  confused with it. notification_pref (all/mentions/muted) is the Step
  18 per-conversation mute setting. last_read_at is the scalable
  read-receipt/unread-count model (a single timestamp per member per
  conversation, not a per-message-per-user row) -- unread count is a
  bounded COUNT(*) WHERE created_at > last_read_at query. removed_at
  marks a former member: their row is kept (so history/audit stays
  coherent) as a permanent record. Note this table's OWN RLS policy does
  NOT read its own removed_at column at all -- visibility is entirely
  gated by chat_conversation_active_members (see above), which is what a
  member's own leave/removal actually updates. removed_at is
  service-layer/UI-facing history, not itself part of the access-control
  decision; the explicit historical-access policy this step documents is
  enforced by the active-members table, not by this column.
- chat_messages: reply_to_message_id is a nullable composite self-FK
  (ON DELETE SET NULL, since a deleted parent must not break a reply's
  existence -- the reply just loses its quoted-preview link, handled
  safely by the application layer). shared_document_id is a composite FK
  to documents(id, company_id) -- see app.modules.collaboration.service
  for why this reference is NEVER trusted as authorization by itself:
  every read re-resolves it through documents.service.get_document.
  deleted_at is a soft delete; the application layer redacts content
  once set rather than the database ever losing the row (preserves
  reply/pin integrity). RLS: any active member can SELECT every message
  in the conversation, but INSERT/UPDATE/DELETE are further scoped to
  sender_id = current_user (INSERT also allows sender_id IS NULL, for
  system messages) -- defense-in-depth against one member's write
  impersonating another's sender_id, beyond plain membership.
- chat_message_attachments / chat_pinned_messages: scoped to their
  message's (or the pin's own) conversation via a join-through EXISTS;
  membership-only, matching chat_conversation_members' peer-write model
  (any active member may attach to or pin within a conversation they
  belong to -- who specifically is allowed to is an application-layer
  RBAC concern, same pattern as company_role elsewhere in this codebase).
- chat_message_reactions: SELECT is membership-scoped (see every
  reaction in the conversation); INSERT/DELETE additionally require
  user_id = current_user (add/remove your OWN reaction only, per spec).
- chat_notifications: SELECT/UPDATE/DELETE are recipient-private
  (user_id = current_user), the same shape as support_tickets'
  creator-private policy but keyed on the recipient rather than the
  creator. INSERT is company-scoped only (not recipient-restricted):
  a notification is always created by the service layer on behalf of
  its recipient in response to a DIFFERENT user's action (e.g. Alice's
  message notifies Bob), so current_user during INSERT is the actor,
  never the row's own user_id.
- chat_call_sessions / chat_call_participants: session/authorization
  state only -- no media is ever stored here (see the Step 18 report for
  the call architecture decision). Scoped via the session's
  conversation_id; chat_call_sessions' INSERT additionally requires
  initiated_by = current_user (can't spoof who started a call).
  chat_call_participants stays membership-only throughout, including
  INSERT, since inviting OTHER participants is exactly what starting a
  call needs to do (the same peer-write shape as adding a group member).

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-22

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COMPANY_EXPR = "company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid"
_USER_EXPR = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"

_CONVERSATION_TYPES = ("direct", "group", "project_channel")
_CONVERSATION_MEMBER_ROLES = ("owner", "admin", "member")
_NOTIFICATION_PREFS = ("all", "mentions", "muted")
_MESSAGE_TYPES = ("text", "system")
_ATTACHMENT_KINDS = ("file", "image", "voice_note")
_NOTIFICATION_TYPES = (
    "new_message",
    "mention",
    "reply",
    "group_added",
    "group_removed",
    "project_channel_activity",
    "support_ticket_update",
)
_CALL_TYPES = ("voice", "video")
_CALL_STATUSES = ("ringing", "active", "ended", "missed", "declined")
_CALL_PARTICIPANT_STATUSES = ("invited", "ringing", "joined", "declined", "missed", "left")


def _member_exists_expr(conversation_id_col: str) -> str:
    """Membership gate used by every table, including chat_conversations and
    chat_conversation_members themselves.

    Queries chat_conversation_active_members -- the one terminal,
    self-contained table in this schema (its own SELECT policy is a direct
    `user_id = current_user` check, no subquery) -- so this can never form a
    policy cycle back to whatever table it's used on. See the module
    docstring for why this table exists and what two simpler designs it
    replaced.
    """
    return (
        f"EXISTS (SELECT 1 FROM chat_conversation_active_members cam "
        f"WHERE cam.conversation_id = {conversation_id_col} AND cam.user_id = {_USER_EXPR})"
    )


def _peer_or_self_active_member_expr(conversation_id_col: str, user_id_col: str) -> str:
    """chat_conversation_active_members' own INSERT/DELETE gate: allow a row
    for `user_id_col` when the ACTING user is either that same user (self
    join/leave) or already an active member of the conversation (peer
    add/remove). The inner EXISTS is resolved via this table's own direct
    SELECT policy (own-row only), never via this INSERT/DELETE policy
    itself, so it does not recurse -- verified empirically, see the module
    docstring.
    """
    return (
        f"({user_id_col} = {_USER_EXPR} OR EXISTS ("
        f"SELECT 1 FROM chat_conversation_active_members existing "
        f"WHERE existing.conversation_id = {conversation_id_col} AND existing.user_id = {_USER_EXPR}))"
    )


def upgrade() -> None:
    def enum(name: str, values: tuple[str, ...]) -> None:
        values_sql = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {name} AS ENUM ({values_sql})")

    enum("conversation_type", _CONVERSATION_TYPES)
    enum("conversation_member_role", _CONVERSATION_MEMBER_ROLES)
    enum("conversation_notification_pref", _NOTIFICATION_PREFS)
    enum("chat_message_type", _MESSAGE_TYPES)
    enum("message_attachment_kind", _ATTACHMENT_KINDS)
    enum("collaboration_notification_type", _NOTIFICATION_TYPES)
    enum("call_type", _CALL_TYPES)
    enum("call_status", _CALL_STATUSES)
    enum("call_participant_status", _CALL_PARTICIPANT_STATUSES)

    # --- chat_conversations ---
    op.create_table(
        "chat_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", postgresql.ENUM(name="conversation_type", create_type=False), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("id", "company_id", name="uq_chat_conversations_id_company"),
        sa.ForeignKeyConstraint(
            ["project_id", "company_id"], ["projects.id", "projects.company_id"],
            name="fk_chat_conversations_project_company",
        ),
    )
    op.create_index("ix_chat_conversations_company_id", "chat_conversations", ["company_id"])
    op.create_index("ix_chat_conversations_project_id", "chat_conversations", ["project_id"])

    # --- chat_conversation_members ---
    op.create_table(
        "chat_conversation_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", postgresql.ENUM(name="conversation_member_role", create_type=False), nullable=False, server_default="member"),
        sa.Column("notification_pref", postgresql.ENUM(name="conversation_notification_pref", create_type=False), nullable=False, server_default="all"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_read_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("conversation_id", "user_id", name="uq_chat_conversation_members_conversation_user"),
        sa.ForeignKeyConstraint(
            ["conversation_id", "company_id"], ["chat_conversations.id", "chat_conversations.company_id"],
            name="fk_chat_conversation_members_conversation_company", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_chat_conversation_members_company_id", "chat_conversation_members", ["company_id"])
    op.create_index("ix_chat_conversation_members_conversation_id", "chat_conversation_members", ["conversation_id"])
    op.create_index("ix_chat_conversation_members_user_id", "chat_conversation_members", ["user_id"])

    # --- chat_conversation_active_members ---
    # RLS-plumbing only -- see the module docstring. One row per
    # (conversation, currently-active user); no history, no other columns.
    # Kept in sync with chat_conversation_members by the application
    # service layer inside the same transaction as every membership
    # add/remove/soft-remove.
    op.create_table(
        "chat_conversation_active_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("conversation_id", "user_id", name="uq_chat_conversation_active_members_conversation_user"),
        sa.ForeignKeyConstraint(
            ["conversation_id", "company_id"], ["chat_conversations.id", "chat_conversations.company_id"],
            name="fk_chat_conversation_active_members_conversation_company", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_chat_conversation_active_members_company_id", "chat_conversation_active_members", ["company_id"])
    op.create_index("ix_chat_conversation_active_members_conversation_id", "chat_conversation_active_members", ["conversation_id"])
    op.create_index("ix_chat_conversation_active_members_user_id", "chat_conversation_active_members", ["user_id"])

    # --- chat_messages ---
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("message_type", postgresql.ENUM(name="chat_message_type", create_type=False), nullable=False, server_default="text"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("reply_to_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("shared_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("id", "company_id", name="uq_chat_messages_id_company"),
        sa.ForeignKeyConstraint(
            ["conversation_id", "company_id"], ["chat_conversations.id", "chat_conversations.company_id"],
            name="fk_chat_messages_conversation_company", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reply_to_message_id", "company_id"], ["chat_messages.id", "chat_messages.company_id"],
            name="fk_chat_messages_reply_to_company", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["shared_document_id", "company_id"], ["documents.id", "documents.company_id"],
            name="fk_chat_messages_shared_document_company", ondelete="SET NULL",
        ),
    )
    op.create_index("ix_chat_messages_company_id", "chat_messages", ["company_id"])
    op.create_index("ix_chat_messages_conversation_id_created_at", "chat_messages", ["conversation_id", "created_at"])

    # --- chat_message_attachments ---
    op.create_table(
        "chat_message_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", postgresql.ENUM(name="message_attachment_kind", create_type=False), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["message_id", "company_id"], ["chat_messages.id", "chat_messages.company_id"],
            name="fk_chat_message_attachments_message_company", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_chat_message_attachments_company_id", "chat_message_attachments", ["company_id"])
    op.create_index("ix_chat_message_attachments_message_id", "chat_message_attachments", ["message_id"])

    # --- chat_message_reactions ---
    op.create_table(
        "chat_message_reactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("emoji", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("message_id", "user_id", "emoji", name="uq_chat_message_reactions_message_user_emoji"),
        sa.ForeignKeyConstraint(
            ["message_id", "company_id"], ["chat_messages.id", "chat_messages.company_id"],
            name="fk_chat_message_reactions_message_company", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_chat_message_reactions_company_id", "chat_message_reactions", ["company_id"])
    op.create_index("ix_chat_message_reactions_message_id", "chat_message_reactions", ["message_id"])

    # --- chat_pinned_messages ---
    op.create_table(
        "chat_pinned_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pinned_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("conversation_id", "message_id", name="uq_chat_pinned_messages_conversation_message"),
        sa.ForeignKeyConstraint(
            ["conversation_id", "company_id"], ["chat_conversations.id", "chat_conversations.company_id"],
            name="fk_chat_pinned_messages_conversation_company", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id", "company_id"], ["chat_messages.id", "chat_messages.company_id"],
            name="fk_chat_pinned_messages_message_company", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_chat_pinned_messages_company_id", "chat_pinned_messages", ["company_id"])
    op.create_index("ix_chat_pinned_messages_conversation_id", "chat_pinned_messages", ["conversation_id"])

    # --- chat_notifications ---
    op.create_table(
        "chat_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", postgresql.ENUM(name="collaboration_notification_type", create_type=False), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("support_ticket_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_chat_notifications_company_id", "chat_notifications", ["company_id"])
    op.create_index("ix_chat_notifications_user_id_created_at", "chat_notifications", ["user_id", "created_at"])

    # --- chat_call_sessions ---
    op.create_table(
        "chat_call_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("initiated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("call_type", postgresql.ENUM(name="call_type", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM(name="call_status", create_type=False), nullable=False, server_default="ringing"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("id", "company_id", name="uq_chat_call_sessions_id_company"),
        sa.ForeignKeyConstraint(
            ["conversation_id", "company_id"], ["chat_conversations.id", "chat_conversations.company_id"],
            name="fk_chat_call_sessions_conversation_company", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_chat_call_sessions_company_id", "chat_call_sessions", ["company_id"])
    op.create_index("ix_chat_call_sessions_conversation_id", "chat_call_sessions", ["conversation_id"])

    # --- chat_call_participants ---
    op.create_table(
        "chat_call_participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("call_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", postgresql.ENUM(name="call_participant_status", create_type=False), nullable=False, server_default="invited"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("call_session_id", "user_id", name="uq_chat_call_participants_session_user"),
        sa.ForeignKeyConstraint(
            ["call_session_id", "company_id"], ["chat_call_sessions.id", "chat_call_sessions.company_id"],
            name="fk_chat_call_participants_session_company", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_chat_call_participants_company_id", "chat_call_participants", ["company_id"])
    op.create_index("ix_chat_call_participants_session_id", "chat_call_participants", ["call_session_id"])

    # --- RLS: applied only after every table above exists, since several
    # policies reference chat_conversation_active_members (and
    # chat_messages, for the attachment/reaction tables) in an EXISTS
    # subquery -- a policy cannot be created against a table that doesn't
    # exist yet. ---

    # chat_conversation_active_members is the one terminal, self-contained
    # table -- see the module docstring. Its SELECT policy is direct
    # (own-row only, no subquery); INSERT/DELETE allow self or any current
    # peer via _peer_or_self_active_member_expr(), which is safe precisely
    # because the inner EXISTS it uses is resolved through this SAME direct
    # SELECT policy, not through the INSERT/DELETE policy being defined.
    op.execute("ALTER TABLE chat_conversation_active_members ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_conversation_active_members FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_select ON chat_conversation_active_members FOR SELECT "
        f"USING ({_COMPANY_EXPR} AND user_id = {_USER_EXPR})"
    )
    op.execute(
        "CREATE POLICY tenant_isolation_insert ON chat_conversation_active_members FOR INSERT "
        f"WITH CHECK ({_COMPANY_EXPR} AND "
        f"{_peer_or_self_active_member_expr('chat_conversation_active_members.conversation_id', 'chat_conversation_active_members.user_id')})"
    )
    op.execute(
        "CREATE POLICY tenant_isolation_delete ON chat_conversation_active_members FOR DELETE "
        f"USING ({_COMPANY_EXPR} AND "
        f"{_peer_or_self_active_member_expr('chat_conversation_active_members.conversation_id', 'chat_conversation_active_members.user_id')})"
    )

    # chat_conversations: SELECT/UPDATE/DELETE require active membership
    # (via chat_conversation_active_members, a different table -- never
    # itself, so unlike design attempt 2 above, updating this row never
    # invalidates its own post-image visibility). INSERT is deliberately
    # more lenient (company-only): a brand new conversation's row is
    # created before its creator's chat_conversation_active_members row
    # exists, so requiring membership here would be a chicken-and-egg
    # deadlock. The service layer is responsible for inserting the
    # creator's active-membership row in the same transaction -- a data
    # hygiene concern (an orphaned same-company row), never a
    # cross-tenant or unauthorized-access one.
    op.execute("ALTER TABLE chat_conversations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_conversations FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_select ON chat_conversations FOR SELECT "
        f"USING ({_COMPANY_EXPR} AND {_member_exists_expr('chat_conversations.id')})"
    )
    op.execute(
        "CREATE POLICY tenant_isolation_insert ON chat_conversations FOR INSERT "
        f"WITH CHECK ({_COMPANY_EXPR})"
    )
    op.execute(
        "CREATE POLICY tenant_isolation_update ON chat_conversations FOR UPDATE "
        f"USING ({_COMPANY_EXPR} AND {_member_exists_expr('chat_conversations.id')})"
    )
    op.execute(
        "CREATE POLICY tenant_isolation_delete ON chat_conversations FOR DELETE "
        f"USING ({_COMPANY_EXPR} AND {_member_exists_expr('chat_conversations.id')})"
    )

    # Every remaining table uses the same single blanket USING expression
    # via _member_exists_expr(), which always routes through
    # chat_conversation_active_members -- never through each other, never
    # through itself.
    policies = {
        "chat_conversation_members": (
            f"{_COMPANY_EXPR} AND {_member_exists_expr('chat_conversation_members.conversation_id')}"
        ),
        "chat_message_attachments": (
            f"{_COMPANY_EXPR} AND EXISTS (SELECT 1 FROM chat_messages m "
            f"WHERE m.id = chat_message_attachments.message_id AND {_member_exists_expr('m.conversation_id')})"
        ),
        "chat_pinned_messages": f"{_COMPANY_EXPR} AND {_member_exists_expr('chat_pinned_messages.conversation_id')}",
        "chat_call_participants": (
            f"{_COMPANY_EXPR} AND EXISTS (SELECT 1 FROM chat_call_sessions cs "
            f"WHERE cs.id = chat_call_participants.call_session_id AND {_member_exists_expr('cs.conversation_id')})"
        ),
    }
    for table, using_expr in policies.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING ({using_expr})")

    # chat_messages: everyone active in the conversation can read every
    # message (SELECT), but writing is further scoped to your OWN
    # sender_id (edit-own/delete-own, per spec) -- a defense-in-depth
    # tightening beyond plain membership, since membership alone would let
    # any member write a message impersonating another member's sender_id.
    # sender_id IS NULL is allowed on INSERT for system messages.
    _msg_member = _member_exists_expr("chat_messages.conversation_id")
    _msg_own = f"(sender_id = {_USER_EXPR} OR sender_id IS NULL)"
    op.execute("ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_messages FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation_select ON chat_messages FOR SELECT USING ({_COMPANY_EXPR} AND {_msg_member})")
    op.execute(f"CREATE POLICY tenant_isolation_insert ON chat_messages FOR INSERT WITH CHECK ({_COMPANY_EXPR} AND {_msg_member} AND {_msg_own})")
    op.execute(f"CREATE POLICY tenant_isolation_update ON chat_messages FOR UPDATE USING ({_COMPANY_EXPR} AND {_msg_member} AND sender_id = {_USER_EXPR})")
    op.execute(f"CREATE POLICY tenant_isolation_delete ON chat_messages FOR DELETE USING ({_COMPANY_EXPR} AND {_msg_member} AND sender_id = {_USER_EXPR})")

    # chat_message_reactions: everyone active in the conversation can see
    # every reaction, but add/remove is scoped to your OWN user_id (per
    # spec: "add/remove own").
    _reaction_member = (
        "EXISTS (SELECT 1 FROM chat_messages m WHERE m.id = chat_message_reactions.message_id "
        f"AND {_member_exists_expr('m.conversation_id')})"
    )
    op.execute("ALTER TABLE chat_message_reactions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_message_reactions FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation_select ON chat_message_reactions FOR SELECT USING ({_COMPANY_EXPR} AND {_reaction_member})")
    op.execute(f"CREATE POLICY tenant_isolation_insert ON chat_message_reactions FOR INSERT WITH CHECK ({_COMPANY_EXPR} AND {_reaction_member} AND user_id = {_USER_EXPR})")
    op.execute(f"CREATE POLICY tenant_isolation_delete ON chat_message_reactions FOR DELETE USING ({_COMPANY_EXPR} AND {_reaction_member} AND user_id = {_USER_EXPR})")

    # chat_notifications: strictly recipient-private for every read/write
    # command EXCEPT INSERT -- a notification is always created by the
    # SERVICE LAYER on behalf of its recipient in response to some OTHER
    # user's action (e.g. Alice's message notifies Bob), so the acting
    # session's current_user is the actor, never the recipient. INSERT is
    # therefore company-scoped only; every read/write of an existing row
    # (mark-read, list, delete) stays recipient-only.
    op.execute("ALTER TABLE chat_notifications ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_notifications FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation_select ON chat_notifications FOR SELECT USING ({_COMPANY_EXPR} AND user_id = {_USER_EXPR})")
    op.execute(f"CREATE POLICY tenant_isolation_insert ON chat_notifications FOR INSERT WITH CHECK ({_COMPANY_EXPR})")
    op.execute(f"CREATE POLICY tenant_isolation_update ON chat_notifications FOR UPDATE USING ({_COMPANY_EXPR} AND user_id = {_USER_EXPR})")
    op.execute(f"CREATE POLICY tenant_isolation_delete ON chat_notifications FOR DELETE USING ({_COMPANY_EXPR} AND user_id = {_USER_EXPR})")

    # chat_call_sessions: everyone active in the conversation can read/end
    # a session, but starting one (INSERT) is scoped to initiated_by =
    # current_user (defense-in-depth against spoofing who started a call).
    _call_member = _member_exists_expr("chat_call_sessions.conversation_id")
    op.execute("ALTER TABLE chat_call_sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_call_sessions FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation_select ON chat_call_sessions FOR SELECT USING ({_COMPANY_EXPR} AND {_call_member})")
    op.execute(f"CREATE POLICY tenant_isolation_insert ON chat_call_sessions FOR INSERT WITH CHECK ({_COMPANY_EXPR} AND {_call_member} AND initiated_by = {_USER_EXPR})")
    op.execute(f"CREATE POLICY tenant_isolation_update ON chat_call_sessions FOR UPDATE USING ({_COMPANY_EXPR} AND {_call_member})")
    op.execute(f"CREATE POLICY tenant_isolation_delete ON chat_call_sessions FOR DELETE USING ({_COMPANY_EXPR} AND {_call_member})")


def downgrade() -> None:
    op.drop_table("chat_call_participants")
    op.drop_table("chat_call_sessions")
    op.drop_table("chat_notifications")
    op.drop_table("chat_pinned_messages")
    op.drop_table("chat_message_reactions")
    op.drop_table("chat_message_attachments")
    op.drop_table("chat_messages")
    op.drop_table("chat_conversation_members")
    # CASCADE: chat_conversations' own policies (SELECT/UPDATE/DELETE)
    # reference this table, so a plain DROP TABLE is rejected with
    # DependentObjectsStillExist -- CASCADE removes those policies too,
    # which is fine since chat_conversations itself is dropped next.
    op.execute("DROP TABLE chat_conversation_active_members CASCADE")
    op.drop_table("chat_conversations")
    for name in (
        "call_participant_status", "call_status", "call_type",
        "collaboration_notification_type", "message_attachment_kind", "chat_message_type",
        "conversation_notification_pref", "conversation_member_role", "conversation_type",
    ):
        op.execute(f"DROP TYPE {name}")

