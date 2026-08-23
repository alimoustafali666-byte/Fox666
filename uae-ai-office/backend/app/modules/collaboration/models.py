import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, ForeignKeyConstraint, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

CONVERSATION_TYPES: tuple[str, ...] = ("direct", "group", "project_channel")
CONVERSATION_MEMBER_ROLES: tuple[str, ...] = ("owner", "admin", "member")
NOTIFICATION_PREFS: tuple[str, ...] = ("all", "mentions", "muted")
MESSAGE_TYPES: tuple[str, ...] = ("text", "system")
ATTACHMENT_KINDS: tuple[str, ...] = ("file", "image", "voice_note")
NOTIFICATION_TYPES: tuple[str, ...] = (
    "new_message",
    "mention",
    "reply",
    "group_added",
    "group_removed",
    "project_channel_activity",
    "support_ticket_update",
    # Added in migration 0018 (Step 19) -- see that migration's docstring
    # for why Tasks reuses this table rather than building a second
    # notification system.
    "task_assigned",
    "task_reassigned",
    "task_comment",
)
CALL_TYPES: tuple[str, ...] = ("voice", "video")
CALL_STATUSES: tuple[str, ...] = ("ringing", "active", "ended", "missed", "declined")
CALL_PARTICIPANT_STATUSES: tuple[str, ...] = ("invited", "ringing", "joined", "declined", "missed", "left")

conversation_type = ENUM(*CONVERSATION_TYPES, name="conversation_type", create_type=False)
conversation_member_role = ENUM(*CONVERSATION_MEMBER_ROLES, name="conversation_member_role", create_type=False)
conversation_notification_pref = ENUM(
    *NOTIFICATION_PREFS, name="conversation_notification_pref", create_type=False
)
chat_message_type = ENUM(*MESSAGE_TYPES, name="chat_message_type", create_type=False)
message_attachment_kind = ENUM(*ATTACHMENT_KINDS, name="message_attachment_kind", create_type=False)
collaboration_notification_type = ENUM(
    *NOTIFICATION_TYPES, name="collaboration_notification_type", create_type=False
)
call_type = ENUM(*CALL_TYPES, name="call_type", create_type=False)
call_status = ENUM(*CALL_STATUSES, name="call_status", create_type=False)
call_participant_status = ENUM(*CALL_PARTICIPANT_STATUSES, name="call_participant_status", create_type=False)


class Conversation(Base):
    """A DM, group, or project channel. See migration 0017's docstring for
    the full RLS design (chat_conversation_active_members is the real
    membership gate; this table's own policy routes through it, never
    through chat_conversation_members). archived_at is set when the last
    active member leaves, or by an explicit archive action.
    """

    __tablename__ = "chat_conversations"
    __table_args__ = (
        UniqueConstraint("id", "company_id", name="uq_chat_conversations_id_company"),
        ForeignKeyConstraint(
            ["project_id", "company_id"],
            ["projects.id", "projects.company_id"],
            name="fk_chat_conversations_project_company",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(conversation_type)
    name: Mapped[str | None] = mapped_column(nullable=True)
    description: Mapped[str | None] = mapped_column(nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ConversationActiveMember(Base):
    """RLS-plumbing only -- never read directly by application code. One
    row per (conversation, currently-active user); see migration 0017's
    docstring for the full design rationale and the exact write ordering
    required to keep this in sync with ConversationMember without
    tripping Postgres's RLS recursion/post-image rules.
    """

    __tablename__ = "chat_conversation_active_members"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "user_id", name="uq_chat_conversation_active_members_conversation_user"
        ),
        ForeignKeyConstraint(
            ["conversation_id", "company_id"],
            ["chat_conversations.id", "chat_conversations.company_id"],
            name="fk_chat_conversation_active_members_conversation_company",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class ConversationMember(Base):
    """The real, historical roster row -- role/notification_pref/read-state/
    removed_at all live here. `role` is a conversation-level permission
    (owner/admin/member), deliberately a separate concept from
    company_role -- never conflated. removed_at is kept (not deleted) as
    a permanent historical record; it plays NO part in this table's own
    RLS policy (which is gated entirely by ConversationActiveMember).
    """

    __tablename__ = "chat_conversation_members"
    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_chat_conversation_members_conversation_user"),
        ForeignKeyConstraint(
            ["conversation_id", "company_id"],
            ["chat_conversations.id", "chat_conversations.company_id"],
            name="fk_chat_conversation_members_conversation_company",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(conversation_member_role, server_default="member")
    notification_pref: Mapped[str] = mapped_column(conversation_notification_pref, server_default="all")
    joined_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    last_read_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_read_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    removed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Message(Base):
    """A chat message. sender_id NULL means a system message. content is
    plain text only -- NEVER rendered as trusted HTML by the frontend.
    reply_to_message_id degrades safely (ON DELETE SET NULL) if the quoted
    message is later hard-deleted (it never is by this app, but the FK is
    defensive). shared_document_id is a pointer only -- see
    collaboration.service for why it is NEVER trusted as authorization by
    itself; every read re-resolves it through documents.service.
    """

    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("id", "company_id", name="uq_chat_messages_id_company"),
        ForeignKeyConstraint(
            ["conversation_id", "company_id"],
            ["chat_conversations.id", "chat_conversations.company_id"],
            name="fk_chat_messages_conversation_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["reply_to_message_id", "company_id"],
            ["chat_messages.id", "chat_messages.company_id"],
            name="fk_chat_messages_reply_to_company",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["shared_document_id", "company_id"],
            ["documents.id", "documents.company_id"],
            name="fk_chat_messages_shared_document_company",
            ondelete="SET NULL",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    sender_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    message_type: Mapped[str] = mapped_column(chat_message_type, server_default="text")
    content: Mapped[str]
    reply_to_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    shared_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class MessageAttachment(Base):
    """file/image/voice_note. storage_key is the StorageProvider key --
    NEVER exposed to the client directly; downloads always go through a
    signed, short-lived URL (see collaboration.service).
    """

    __tablename__ = "chat_message_attachments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["message_id", "company_id"],
            ["chat_messages.id", "chat_messages.company_id"],
            name="fk_chat_message_attachments_message_company",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(message_attachment_kind)
    file_name: Mapped[str]
    file_type: Mapped[str]
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str]
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class MessageReaction(Base):
    """emoji is validated against a bounded allowlist by the service layer
    (never arbitrary text) -- see collaboration.service.ALLOWED_REACTIONS.
    """

    __tablename__ = "chat_message_reactions"
    __table_args__ = (
        UniqueConstraint("message_id", "user_id", "emoji", name="uq_chat_message_reactions_message_user_emoji"),
        ForeignKeyConstraint(
            ["message_id", "company_id"],
            ["chat_messages.id", "chat_messages.company_id"],
            name="fk_chat_message_reactions_message_company",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    emoji: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class PinnedMessage(Base):
    __tablename__ = "chat_pinned_messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "message_id", name="uq_chat_pinned_messages_conversation_message"),
        ForeignKeyConstraint(
            ["conversation_id", "company_id"],
            ["chat_conversations.id", "chat_conversations.company_id"],
            name="fk_chat_pinned_messages_conversation_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["message_id", "company_id"],
            ["chat_messages.id", "chat_messages.company_id"],
            name="fk_chat_pinned_messages_message_company",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    pinned_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    pinned_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class ChatNotification(Base):
    """Recipient-private. Always INSERTed by the service layer on behalf
    of its recipient (current_user during INSERT is the actor who
    triggered it, e.g. the message sender -- never the recipient); see
    migration 0017's docstring for why the RLS policy allows this.
    """

    __tablename__ = "chat_notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(collaboration_notification_type)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    support_ticket_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    title: Mapped[str]
    body: Mapped[str | None] = mapped_column(nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class CallSession(Base):
    """Session/authorization state only -- no media is ever stored here.
    See the Step 18 report for the call architecture decision (1:1 real
    WebRTC via a signaling relay; group calls are architecture-only).
    """

    __tablename__ = "chat_call_sessions"
    __table_args__ = (
        UniqueConstraint("id", "company_id", name="uq_chat_call_sessions_id_company"),
        ForeignKeyConstraint(
            ["conversation_id", "company_id"],
            ["chat_conversations.id", "chat_conversations.company_id"],
            name="fk_chat_call_sessions_conversation_company",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    initiated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    call_type: Mapped[str] = mapped_column(call_type)
    status: Mapped[str] = mapped_column(call_status, server_default="ringing")
    started_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_reason: Mapped[str | None] = mapped_column(nullable=True)


class CallParticipant(Base):
    __tablename__ = "chat_call_participants"
    __table_args__ = (
        UniqueConstraint("call_session_id", "user_id", name="uq_chat_call_participants_session_user"),
        ForeignKeyConstraint(
            ["call_session_id", "company_id"],
            ["chat_call_sessions.id", "chat_call_sessions.company_id"],
            name="fk_chat_call_participants_session_company",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    call_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(call_participant_status, server_default="invited")
    joined_at: Mapped[datetime | None] = mapped_column(nullable=True)
    left_at: Mapped[datetime | None] = mapped_column(nullable=True)

