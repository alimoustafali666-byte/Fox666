import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.modules.collaboration.models import (
    CallParticipant,
    CallSession,
    ChatNotification,
    Conversation,
    ConversationActiveMember,
    ConversationMember,
    Message,
    MessageAttachment,
    MessageReaction,
    PinnedMessage,
)

# --- conversations ---


def create_conversation(
    db: Session,
    *,
    id: uuid.UUID,
    company_id: uuid.UUID,
    type: str,
    name: str | None,
    description: str | None,
    project_id: uuid.UUID | None,
    created_by: uuid.UUID,
) -> Conversation:
    now = datetime.now(UTC)
    conversation = Conversation(
        id=id,
        company_id=company_id,
        type=type,
        name=name,
        description=description,
        project_id=project_id,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    db.add(conversation)
    db.flush()
    return conversation


def get_conversation_by_id(db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation | None:
    return db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.company_id == company_id)
    ).scalar_one_or_none()


def list_conversations_for_user(
    db: Session,
    *,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None = None,
) -> list[Conversation]:
    query = (
        select(Conversation)
        .join(
            ConversationActiveMember,
            and_(
                ConversationActiveMember.conversation_id == Conversation.id,
                ConversationActiveMember.company_id == Conversation.company_id,
            ),
        )
        .where(
            Conversation.company_id == company_id,
            ConversationActiveMember.user_id == user_id,
            Conversation.archived_at.is_(None),
        )
    )
    if cursor is not None:
        cursor_updated_at, cursor_id = cursor
        query = query.where(
            or_(
                Conversation.updated_at < cursor_updated_at,
                and_(Conversation.updated_at == cursor_updated_at, Conversation.id < cursor_id),
            )
        )
    query = query.order_by(Conversation.updated_at.desc(), Conversation.id.desc()).limit(limit)
    return list(db.execute(query).scalars())


def find_existing_direct_conversation(
    db: Session, *, company_id: uuid.UUID, user_a: uuid.UUID, user_b: uuid.UUID
) -> Conversation | None:
    """A non-archived DIRECT conversation both user_a and user_b are
    currently active members of. No separate "exactly 2 members" count
    check is needed: a DIRECT conversation's membership never changes
    after creation (service.py's add/remove-member endpoints reject
    type="direct" outright), so type == "direct" already guarantees
    exactly 2 active members structurally.

    Deliberately joins against ConversationMember (the roster table, RLS-
    visible to any active member of the SAME conversation), never
    ConversationActiveMember: that table's SELECT policy is strictly
    own-row (`user_id = current_user`, see migration 0017's docstring),
    so user_a's session can NEVER see user_b's row there directly --
    confirmed via a direct repro where this query returned nothing even
    though both rows existed. ConversationMember has no such restriction
    (its own SELECT policy is membership-gated, not row-owner-gated), so
    this is both correct and RLS-consistent.
    """
    m1 = ConversationMember
    m2 = ConversationMember.__table__.alias("m2")
    query = (
        select(Conversation)
        .join(m1, and_(m1.conversation_id == Conversation.id, m1.company_id == Conversation.company_id))
        .join(m2, and_(m2.c.conversation_id == Conversation.id, m2.c.company_id == Conversation.company_id))
        .where(
            Conversation.company_id == company_id,
            Conversation.type == "direct",
            Conversation.archived_at.is_(None),
            m1.user_id == user_a,
            m1.removed_at.is_(None),
            m2.c.user_id == user_b,
            m2.c.removed_at.is_(None),
        )
    )
    return db.execute(query).scalars().first()


def touch_conversation(db: Session, conversation: Conversation) -> Conversation:
    conversation.updated_at = datetime.now(UTC)
    db.flush()
    return conversation


def rename_conversation(
    db: Session, conversation: Conversation, *, name: str | None, description: str | None
) -> Conversation:
    conversation.name = name
    conversation.description = description
    conversation.updated_at = datetime.now(UTC)
    db.flush()
    return conversation


def archive_conversation(db: Session, conversation: Conversation) -> Conversation:
    conversation.archived_at = datetime.now(UTC)
    db.flush()
    return conversation


# --- active members (RLS plumbing) ---


def add_active_member(db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """A plain Core INSERT, deliberately NOT `db.add(...)` +
    `db.flush()`: the ORM's default flush uses `INSERT ... RETURNING` to
    fetch back the server-generated `id`, and Postgres applies the SAME
    "post-image must satisfy the table's SELECT policy" rule to
    INSERT...RETURNING as it does to UPDATE (see migration 0017's
    docstring on design attempt 2, which hit this for UPDATE). Since this
    table's SELECT policy is strictly own-row (`user_id = current_user`),
    a PEER insert (the acting user adding someone ELSE, e.g. group
    invites) would be silently rejected on RETURNING even though its own
    WITH CHECK correctly allows the write -- confirmed via a direct psql
    repro. A Core INSERT with no RETURNING clause sidesteps this
    entirely; the caller here never needs the generated id back.
    """
    db.execute(
        ConversationActiveMember.__table__.insert().values(
            id=uuid.uuid4(), company_id=company_id, conversation_id=conversation_id, user_id=user_id,
            created_at=datetime.now(UTC),
        )
    )
    db.flush()


def remove_active_member(
    db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID, user_id: uuid.UUID, acting_user_id: uuid.UUID
) -> None:
    """DELETE (and UPDATE) under Postgres RLS require the target row to
    satisfy the table's SELECT policy BEFORE the command-specific USING
    clause is even consulted -- confirmed via a direct repro where a
    DELETE policy of `USING (true)` (unconditional) still matched zero
    rows for a row the SELECT policy hid. Since
    chat_conversation_active_members' SELECT policy is strictly own-row
    (`user_id = current_user` -- required to keep it the one non-
    recursive terminal node, see migration 0017's docstring), NO session
    other than the row's own user can ever delete it directly -- not
    even via a permissively-written DELETE policy.

    So for a PEER removal (an admin removing someone else, which
    service.py has already authorized via _require_admin before calling
    this), this function briefly sets app.current_user_id to `user_id`
    (the row being removed) for exactly this one DELETE, then restores it
    to `acting_user_id` (the real caller) immediately after. This is not
    a privilege escalation: the write it performs is narrowly scoped to
    the exact row the application already decided, via ordinary RBAC, to
    remove -- the same shape as chat_notifications' INSERT being
    company-scoped rather than recipient-scoped, because the service
    layer is writing "on behalf of" a different identity than the
    session's real actor. For a SELF removal (user_id == acting_user_id,
    e.g. leaving a conversation), this is a no-op identity switch.
    """
    from app.db.session import set_user_context

    if user_id != acting_user_id:
        set_user_context(db, user_id)
    try:
        db.execute(
            ConversationActiveMember.__table__.delete().where(
                ConversationActiveMember.company_id == company_id,
                ConversationActiveMember.conversation_id == conversation_id,
                ConversationActiveMember.user_id == user_id,
            )
        )
        db.flush()
    finally:
        if user_id != acting_user_id:
            set_user_context(db, acting_user_id)


def count_active_members(db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID) -> int:
    """Deliberately counts ConversationMember (the roster table, RLS-
    visible to any active member of the conversation), NEVER
    ConversationActiveMember: that table's SELECT policy is strictly
    own-row (`user_id = current_user`), so a plain COUNT(*) against it
    would only ever see the CALLING user's own row (at most 1),
    regardless of the conversation's real size -- confirmed via a direct
    repro. This would have silently made the max-group-size check in
    service.py a no-op. ConversationMember has no such restriction.
    """
    return db.execute(
        select(func.count()).where(
            ConversationMember.company_id == company_id,
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.removed_at.is_(None),
        )
    ).scalar_one()


def is_active_member(db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Only ever safe to call with `user_id` equal to the CURRENT
    session's own user: ConversationActiveMember's SELECT policy is
    strictly own-row (`user_id = current_user`), so checking a DIFFERENT
    user's membership here would always return False regardless of the
    real state (RLS hides the row entirely, it isn't just filtered out
    by this query). service.py's only call site passes actor_user_id for
    exactly this reason. To check whether some OTHER user is a member,
    query ConversationMember (the roster) instead.
    """
    return (
        db.execute(
            select(ConversationActiveMember.id).where(
                ConversationActiveMember.company_id == company_id,
                ConversationActiveMember.conversation_id == conversation_id,
                ConversationActiveMember.user_id == user_id,
            )
        ).scalar_one_or_none()
        is not None
    )


# --- members (roster) ---


def add_member(
    db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID, user_id: uuid.UUID, role: str
) -> ConversationMember:
    member = ConversationMember(
        company_id=company_id,
        conversation_id=conversation_id,
        user_id=user_id,
        role=role,
        notification_pref="all",
        joined_at=datetime.now(UTC),
    )
    db.add(member)
    db.flush()
    return member


def get_member(
    db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID, user_id: uuid.UUID
) -> ConversationMember | None:
    return db.execute(
        select(ConversationMember).where(
            ConversationMember.company_id == company_id,
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
        )
    ).scalar_one_or_none()


def list_active_members(db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID) -> list[ConversationMember]:
    return list(
        db.execute(
            select(ConversationMember)
            .where(
                ConversationMember.company_id == company_id,
                ConversationMember.conversation_id == conversation_id,
                ConversationMember.removed_at.is_(None),
            )
            .order_by(ConversationMember.joined_at.asc())
        ).scalars()
    )


def soft_remove_member(db: Session, member: ConversationMember) -> ConversationMember:
    member.removed_at = datetime.now(UTC)
    db.flush()
    return member


def update_member_role(db: Session, member: ConversationMember, *, role: str) -> ConversationMember:
    member.role = role
    db.flush()
    return member


def update_member_notification_pref(db: Session, member: ConversationMember, *, pref: str) -> ConversationMember:
    member.notification_pref = pref
    db.flush()
    return member


def update_last_read(
    db: Session, member: ConversationMember, *, message_id: uuid.UUID, read_at: datetime
) -> ConversationMember:
    member.last_read_message_id = message_id
    member.last_read_at = read_at
    db.flush()
    return member


def get_members_for_conversations(
    db: Session, *, company_id: uuid.UUID, user_id: uuid.UUID, conversation_ids: list[uuid.UUID]
) -> dict[uuid.UUID, ConversationMember]:
    if not conversation_ids:
        return {}
    rows = list(
        db.execute(
            select(ConversationMember).where(
                ConversationMember.company_id == company_id,
                ConversationMember.user_id == user_id,
                ConversationMember.conversation_id.in_(conversation_ids),
            )
        ).scalars()
    )
    return {row.conversation_id: row for row in rows}


def count_admins_and_owners(db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count()).where(
            ConversationMember.company_id == company_id,
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.removed_at.is_(None),
            ConversationMember.role.in_(("owner", "admin")),
        )
    ).scalar_one()


def unread_count(db: Session, member: ConversationMember) -> int:
    """Bounded COUNT(*) against the scalable last_read_at model -- never a
    per-message-per-user row.
    """
    if member.last_read_at is None:
        return db.execute(
            select(func.count()).where(
                Message.company_id == member.company_id,
                Message.conversation_id == member.conversation_id,
                Message.deleted_at.is_(None),
            )
        ).scalar_one()
    return db.execute(
        select(func.count()).where(
            Message.company_id == member.company_id,
            Message.conversation_id == member.conversation_id,
            Message.created_at > member.last_read_at,
            Message.deleted_at.is_(None),
        )
    ).scalar_one()


# --- messages ---


def create_message(
    db: Session,
    *,
    id: uuid.UUID,
    company_id: uuid.UUID,
    conversation_id: uuid.UUID,
    sender_id: uuid.UUID | None,
    message_type: str,
    content: str,
    reply_to_message_id: uuid.UUID | None,
    shared_document_id: uuid.UUID | None,
) -> Message:
    message = Message(
        id=id,
        company_id=company_id,
        conversation_id=conversation_id,
        sender_id=sender_id,
        message_type=message_type,
        content=content,
        reply_to_message_id=reply_to_message_id,
        shared_document_id=shared_document_id,
        created_at=datetime.now(UTC),
    )
    db.add(message)
    db.flush()
    return message


def get_message_by_id(db: Session, *, company_id: uuid.UUID, message_id: uuid.UUID) -> Message | None:
    return db.execute(
        select(Message).where(Message.id == message_id, Message.company_id == company_id)
    ).scalar_one_or_none()


def list_messages(
    db: Session,
    *,
    company_id: uuid.UUID,
    conversation_id: uuid.UUID,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None = None,
) -> list[Message]:
    query = select(Message).where(Message.company_id == company_id, Message.conversation_id == conversation_id)
    if cursor is not None:
        cursor_created_at, cursor_id = cursor
        query = query.where(
            or_(
                Message.created_at < cursor_created_at,
                and_(Message.created_at == cursor_created_at, Message.id < cursor_id),
            )
        )
    query = query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit)
    return list(db.execute(query).scalars())


def list_recent_messages(db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID, max_messages: int) -> list[Message]:
    rows = list(
        db.execute(
            select(Message)
            .where(
                Message.company_id == company_id,
                Message.conversation_id == conversation_id,
                Message.deleted_at.is_(None),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(max_messages)
        ).scalars()
    )
    rows.reverse()
    return rows


def list_unread_messages(
    db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID, since: datetime | None, max_messages: int
) -> list[Message]:
    query = select(Message).where(
        Message.company_id == company_id,
        Message.conversation_id == conversation_id,
        Message.deleted_at.is_(None),
    )
    if since is not None:
        query = query.where(Message.created_at > since)
    query = query.order_by(Message.created_at.asc()).limit(max_messages)
    return list(db.execute(query).scalars())


def edit_message(db: Session, message: Message, *, content: str) -> Message:
    message.content = content
    message.edited_at = datetime.now(UTC)
    db.flush()
    return message


def soft_delete_message(db: Session, message: Message) -> Message:
    message.deleted_at = datetime.now(UTC)
    message.content = ""
    db.flush()
    return message


def search_messages(
    db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID, query_text: str, limit: int
) -> list[Message]:
    """Postgres-native full text search (plainto_tsquery), bounded to a
    single conversation the caller has already authorized. Deliberately
    NOT Elasticsearch/OpenSearch, per spec.
    """
    ts_query = func.plainto_tsquery("simple", query_text)
    return list(
        db.execute(
            select(Message)
            .where(
                Message.company_id == company_id,
                Message.conversation_id == conversation_id,
                Message.deleted_at.is_(None),
                func.to_tsvector("simple", Message.content).op("@@")(ts_query),
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
        ).scalars()
    )


# --- attachments ---


def create_attachment(
    db: Session,
    *,
    id: uuid.UUID,
    company_id: uuid.UUID,
    message_id: uuid.UUID,
    kind: str,
    file_name: str,
    file_type: str,
    file_size_bytes: int,
    storage_key: str,
    duration_seconds: int | None,
) -> MessageAttachment:
    attachment = MessageAttachment(
        id=id,
        company_id=company_id,
        message_id=message_id,
        kind=kind,
        file_name=file_name,
        file_type=file_type,
        file_size_bytes=file_size_bytes,
        storage_key=storage_key,
        duration_seconds=duration_seconds,
        created_at=datetime.now(UTC),
    )
    db.add(attachment)
    db.flush()
    return attachment


def get_attachment_by_id(db: Session, *, company_id: uuid.UUID, attachment_id: uuid.UUID) -> MessageAttachment | None:
    return db.execute(
        select(MessageAttachment).where(
            MessageAttachment.id == attachment_id, MessageAttachment.company_id == company_id
        )
    ).scalar_one_or_none()


def list_attachments_for_messages(
    db: Session, *, company_id: uuid.UUID, message_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[MessageAttachment]]:
    if not message_ids:
        return {}
    rows = list(
        db.execute(
            select(MessageAttachment).where(
                MessageAttachment.company_id == company_id, MessageAttachment.message_id.in_(message_ids)
            )
        ).scalars()
    )
    result: dict[uuid.UUID, list[MessageAttachment]] = {}
    for row in rows:
        result.setdefault(row.message_id, []).append(row)
    return result


def list_attachments_for_conversation(
    db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID, kind: str | None, limit: int
) -> list[MessageAttachment]:
    query = (
        select(MessageAttachment)
        .join(Message, and_(Message.id == MessageAttachment.message_id, Message.company_id == MessageAttachment.company_id))
        .where(
            MessageAttachment.company_id == company_id,
            Message.conversation_id == conversation_id,
            Message.deleted_at.is_(None),
        )
    )
    if kind is not None:
        query = query.where(MessageAttachment.kind == kind)
    query = query.order_by(MessageAttachment.created_at.desc()).limit(limit)
    return list(db.execute(query).scalars())


# --- reactions ---


def add_reaction(
    db: Session, *, id: uuid.UUID, company_id: uuid.UUID, message_id: uuid.UUID, user_id: uuid.UUID, emoji: str
) -> MessageReaction:
    reaction = MessageReaction(
        id=id, company_id=company_id, message_id=message_id, user_id=user_id, emoji=emoji, created_at=datetime.now(UTC)
    )
    db.add(reaction)
    db.flush()
    return reaction


def remove_reaction(db: Session, *, company_id: uuid.UUID, message_id: uuid.UUID, user_id: uuid.UUID, emoji: str) -> None:
    db.execute(
        MessageReaction.__table__.delete().where(
            MessageReaction.company_id == company_id,
            MessageReaction.message_id == message_id,
            MessageReaction.user_id == user_id,
            MessageReaction.emoji == emoji,
        )
    )
    db.flush()


def list_reactions_for_messages(
    db: Session, *, company_id: uuid.UUID, message_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[MessageReaction]]:
    if not message_ids:
        return {}
    rows = list(
        db.execute(
            select(MessageReaction).where(
                MessageReaction.company_id == company_id, MessageReaction.message_id.in_(message_ids)
            )
        ).scalars()
    )
    result: dict[uuid.UUID, list[MessageReaction]] = {}
    for row in rows:
        result.setdefault(row.message_id, []).append(row)
    return result


# --- pinned messages ---


def pin_message(
    db: Session, *, id: uuid.UUID, company_id: uuid.UUID, conversation_id: uuid.UUID, message_id: uuid.UUID, pinned_by: uuid.UUID
) -> PinnedMessage:
    pin = PinnedMessage(
        id=id,
        company_id=company_id,
        conversation_id=conversation_id,
        message_id=message_id,
        pinned_by=pinned_by,
        pinned_at=datetime.now(UTC),
    )
    db.add(pin)
    db.flush()
    return pin


def unpin_message(db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID, message_id: uuid.UUID) -> None:
    db.execute(
        PinnedMessage.__table__.delete().where(
            PinnedMessage.company_id == company_id,
            PinnedMessage.conversation_id == conversation_id,
            PinnedMessage.message_id == message_id,
        )
    )
    db.flush()


def list_pinned_messages(db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID) -> list[PinnedMessage]:
    return list(
        db.execute(
            select(PinnedMessage)
            .where(PinnedMessage.company_id == company_id, PinnedMessage.conversation_id == conversation_id)
            .order_by(PinnedMessage.pinned_at.desc())
        ).scalars()
    )


def get_pin(db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID, message_id: uuid.UUID) -> PinnedMessage | None:
    return db.execute(
        select(PinnedMessage).where(
            PinnedMessage.company_id == company_id,
            PinnedMessage.conversation_id == conversation_id,
            PinnedMessage.message_id == message_id,
        )
    ).scalar_one_or_none()


# --- notifications ---


def create_notification(
    db: Session,
    *,
    id: uuid.UUID,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    type: str,
    conversation_id: uuid.UUID | None,
    message_id: uuid.UUID | None,
    support_ticket_id: uuid.UUID | None,
    title: str,
    body: str | None,
    task_id: uuid.UUID | None = None,
) -> ChatNotification:
    notification = ChatNotification(
        id=id,
        company_id=company_id,
        user_id=user_id,
        type=type,
        conversation_id=conversation_id,
        message_id=message_id,
        support_ticket_id=support_ticket_id,
        task_id=task_id,
        title=title,
        body=body,
        created_at=datetime.now(UTC),
    )
    db.add(notification)
    db.flush()
    return notification


def list_notifications(
    db: Session, *, company_id: uuid.UUID, user_id: uuid.UUID, unread_only: bool, limit: int
) -> list[ChatNotification]:
    query = select(ChatNotification).where(ChatNotification.company_id == company_id, ChatNotification.user_id == user_id)
    if unread_only:
        query = query.where(ChatNotification.read_at.is_(None))
    query = query.order_by(ChatNotification.created_at.desc()).limit(limit)
    return list(db.execute(query).scalars())


def count_unread_notifications(db: Session, *, company_id: uuid.UUID, user_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count()).where(
            ChatNotification.company_id == company_id,
            ChatNotification.user_id == user_id,
            ChatNotification.read_at.is_(None),
        )
    ).scalar_one()


def get_notification(db: Session, *, company_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID) -> ChatNotification | None:
    return db.execute(
        select(ChatNotification).where(
            ChatNotification.id == notification_id,
            ChatNotification.company_id == company_id,
            ChatNotification.user_id == user_id,
        )
    ).scalar_one_or_none()


def mark_notification_read(db: Session, notification: ChatNotification) -> ChatNotification:
    notification.read_at = datetime.now(UTC)
    db.flush()
    return notification


def mark_all_notifications_read(db: Session, *, company_id: uuid.UUID, user_id: uuid.UUID) -> int:
    result = db.execute(
        ChatNotification.__table__.update()
        .where(
            ChatNotification.company_id == company_id,
            ChatNotification.user_id == user_id,
            ChatNotification.read_at.is_(None),
        )
        .values(read_at=datetime.now(UTC))
    )
    db.flush()
    return result.rowcount or 0


# --- calls ---


def create_call_session(
    db: Session, *, id: uuid.UUID, company_id: uuid.UUID, conversation_id: uuid.UUID, initiated_by: uuid.UUID, call_type: str
) -> CallSession:
    session = CallSession(
        id=id,
        company_id=company_id,
        conversation_id=conversation_id,
        initiated_by=initiated_by,
        call_type=call_type,
        status="ringing",
        started_at=datetime.now(UTC),
    )
    db.add(session)
    db.flush()
    return session


def get_call_session(db: Session, *, company_id: uuid.UUID, call_session_id: uuid.UUID) -> CallSession | None:
    return db.execute(
        select(CallSession).where(CallSession.id == call_session_id, CallSession.company_id == company_id)
    ).scalar_one_or_none()


def get_active_call_session_for_conversation(db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID) -> CallSession | None:
    return db.execute(
        select(CallSession).where(
            CallSession.company_id == company_id,
            CallSession.conversation_id == conversation_id,
            CallSession.status.in_(("ringing", "active")),
        )
    ).scalar_one_or_none()


def update_call_status(db: Session, session: CallSession, *, status: str, ended_reason: str | None = None) -> CallSession:
    session.status = status
    if status in ("ended", "missed", "declined"):
        session.ended_at = datetime.now(UTC)
        session.ended_reason = ended_reason
    db.flush()
    return session


def add_call_participant(
    db: Session, *, id: uuid.UUID, company_id: uuid.UUID, call_session_id: uuid.UUID, user_id: uuid.UUID
) -> CallParticipant:
    participant = CallParticipant(
        id=id, company_id=company_id, call_session_id=call_session_id, user_id=user_id, status="invited"
    )
    db.add(participant)
    db.flush()
    return participant


def get_call_participant(db: Session, *, company_id: uuid.UUID, call_session_id: uuid.UUID, user_id: uuid.UUID) -> CallParticipant | None:
    return db.execute(
        select(CallParticipant).where(
            CallParticipant.company_id == company_id,
            CallParticipant.call_session_id == call_session_id,
            CallParticipant.user_id == user_id,
        )
    ).scalar_one_or_none()


def list_call_participants(db: Session, *, company_id: uuid.UUID, call_session_id: uuid.UUID) -> list[CallParticipant]:
    return list(
        db.execute(
            select(CallParticipant).where(
                CallParticipant.company_id == company_id, CallParticipant.call_session_id == call_session_id
            )
        ).scalars()
    )


def update_call_participant_status(
    db: Session, participant: CallParticipant, *, status: str
) -> CallParticipant:
    participant.status = status
    now = datetime.now(UTC)
    if status == "joined":
        participant.joined_at = now
    elif status in ("left", "declined", "missed"):
        participant.left_at = now
    db.flush()
    return participant

