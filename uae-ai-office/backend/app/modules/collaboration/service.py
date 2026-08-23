"""Business logic and authorization for Step 18 Company Communication &
AI Collaboration. Every function here that touches an existing
conversation starts by re-resolving membership through
_require_active_conversation() -- never trusts a conversation_id or
message_id from client input without that check, even though RLS
already enforces the same boundary at the database level (defense in
depth, same discipline as every other module in this codebase).

MEMBERSHIP WRITE ORDERING (security-critical): every function that adds
or removes a chat_conversation_active_members row follows the exact
ordering documented in migration 0017 to avoid tripping Postgres's RLS
recursion/post-image rules -- see that migration's docstring for the
full explanation. In short: add the active-member row BEFORE any other
write that depends on it; remove it LAST, after chat_conversation_members
and chat_conversations have already been updated.

AI PERMISSION BOUNDARY (security-critical, Step 18 spec section on this
exact topic): every AI collaboration function
(summarize_conversation/summarize_unread/extract_decisions/
extract_action_items/ask_about_conversation) follows the same fixed
pipeline: authenticated user -> tenant context (already resolved by the
router's TenantContext dependency) -> verify conversation membership
(_require_active_conversation) -> retrieve ONLY this conversation's
already-authorized messages, bounded in count -> hand that bounded
context to LLMProvider -> return a structured, citation-validated
response. The model is never given direct DB access, never given an
arbitrary conversation_id to look up itself, and this module never mixes
context from Ask Your Business, the Support Assistant, or another
conversation into a single call -- each is a distinct trust boundary
(same principle already established for the Support Assistant in Step
17; see app.modules.support.assistant_service's module docstring for the
precedent). Message content handed to the provider is DATA, never
instructions -- same discipline as document content in Ask Your
Business.

MENTIONS resolve ONLY against the conversation's real, currently ACTIVE
membership (see _resolve_mentions) -- a mention can never expose or
notify a non-member's identity, and @all/@channel only ever expands to
the real active roster at send time.

DOCUMENT SHARING never trusts a message's shared_document_id as
authorization by itself. share_document_in_message re-validates the
SENDER can access the document (via documents.service.get_document,
company-scoped) before persisting the reference, and every later read
of a shared-document message re-resolves it through the SAME
documents.service.get_document call for the READER -- so a recipient
who can see the message but isn't otherwise authorized for the document
still cannot open it (sharing a message never grants document access by
itself, per spec).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMMalformedOutputError,
    LLMOperationError,
    LLMUnavailable,
)
from app.core.llm.factory import get_llm_provider
from app.core.llm.provider import (
    CollaborationInsightsRequest,
    CollaborationMessageContextItem,
    DocumentContextItem,
    GroundedAnswerRequest,
)
from app.core.storage.exceptions import ObjectNotFoundError
from app.core.storage.factory import get_storage_provider
from app.core.storage.keys import build_chat_attachment_object_key
from app.modules.audit_log.service import record_audit_event
from app.modules.auth.models import User
from app.modules.collaboration import repository
from app.modules.collaboration.attachment_validation import (
    IMAGE_FAMILIES,
    detect_and_validate_attachment_type,
)
from app.modules.collaboration.exceptions import (
    AttachmentNotFoundError,
    AttachmentTooLargeError,
    BlankMessageError,
    CallAlreadyActiveError,
    CallSessionNotFoundError,
    CannotDeleteOthersMessageError,
    CannotEditOthersMessageError,
    CannotRemoveLastAdminError,
    CollaborationAssistantUnavailableError,
    CollaborationRateLimitedError,
    ConversationNotFoundError,
    DocumentShareNotAuthorizedError,
    GroupSizeLimitExceededError,
    InvalidConversationTypeError,
    InvalidReactionEmojiError,
    MessageNotFoundError,
    MessageTooLongError,
    NotConversationAdminError,
    NotConversationMemberError,
    NotificationNotFoundError,
    SearchQueryTooLongError,
    UnsupportedAttachmentTypeError,
    VoiceNoteTooLongError,
)
from app.modules.collaboration.models import (
    CallSession,
    Conversation,
    ConversationMember,
    Message,
)
from app.modules.collaboration.rate_limit import ai_insights_rate_limiter, message_send_rate_limiter
from app.modules.documents.exceptions import DocumentNotFoundError
from app.modules.documents.service import get_document
from app.modules.documents.upload_stream import measure_and_checksum
from app.modules.projects.service import get_project
from app.modules.tenancy.models import CompanyMember

ALLOWED_REACTIONS: frozenset[str] = frozenset(
    {"thumbsup", "thumbsdown", "heart", "laugh", "surprised", "sad", "pray", "party"}
)

_MENTION_ALL_TOKENS = ("@all", "@channel")


# --- small internal helpers ---


def _require_active_conversation(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation:
    """Deliberately identical 404 whether the conversation doesn't exist,
    belongs to another company, or the caller is not (or is no longer) an
    active member -- IDOR protection, same rationale as every other
    *NotFoundError in this codebase. Defense-in-depth on top of RLS
    (which already makes the row physically unreadable in this session).
    """
    conversation = repository.get_conversation_by_id(db, company_id=company_id, conversation_id=conversation_id)
    if conversation is None:
        raise ConversationNotFoundError("Conversation not found.")
    if not repository.is_active_member(
        db, company_id=company_id, conversation_id=conversation_id, user_id=actor_user_id
    ):
        raise ConversationNotFoundError("Conversation not found.")
    return conversation


def _require_active_member_row(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID
) -> ConversationMember:
    member = repository.get_member(db, company_id=company_id, conversation_id=conversation_id, user_id=actor_user_id)
    if member is None or member.removed_at is not None:
        raise NotConversationMemberError("You are not an active member of this conversation.")
    return member


def _require_admin(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID
) -> ConversationMember:
    member = _require_active_member_row(
        db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id
    )
    if member.role not in ("owner", "admin"):
        raise NotConversationAdminError("Only a conversation owner or admin may perform this action.")
    return member


def _is_company_member(db: Session, *, company_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    return (
        db.execute(
            select(CompanyMember.id).where(CompanyMember.company_id == company_id, CompanyMember.user_id == user_id)
        ).scalar_one_or_none()
        is not None
    )


def _get_message_or_404(db: Session, *, company_id: uuid.UUID, message_id: uuid.UUID) -> Message:
    message = repository.get_message_by_id(db, company_id=company_id, message_id=message_id)
    if message is None:
        raise MessageNotFoundError("Message not found.")
    return message


# --- conversation creation ---


def create_direct_conversation(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, other_user_id: uuid.UUID, ip_address: str | None
) -> Conversation:
    if other_user_id == actor_user_id:
        raise InvalidConversationTypeError("Cannot start a direct conversation with yourself.")
    if not _is_company_member(db, company_id=company_id, user_id=other_user_id):
        raise NotConversationMemberError("That user is not a member of your company.")

    existing = repository.find_existing_direct_conversation(
        db, company_id=company_id, user_a=actor_user_id, user_b=other_user_id
    )
    if existing is not None:
        return existing

    conversation = repository.create_conversation(
        db,
        id=uuid.uuid4(),
        company_id=company_id,
        type="direct",
        name=None,
        description=None,
        project_id=None,
        created_by=actor_user_id,
    )
    # Ordering: self first (self-insert), then peer (peer-insert, gated by
    # the acting user's own just-created active-membership row) -- see
    # migration 0017's docstring.
    repository.add_active_member(db, company_id=company_id, conversation_id=conversation.id, user_id=actor_user_id)
    repository.add_active_member(db, company_id=company_id, conversation_id=conversation.id, user_id=other_user_id)
    repository.add_member(db, company_id=company_id, conversation_id=conversation.id, user_id=actor_user_id, role="member")
    repository.add_member(db, company_id=company_id, conversation_id=conversation.id, user_id=other_user_id, role="member")

    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="collaboration.conversation_created",
        resource_type="chat_conversation", resource_id=conversation.id, metadata={"type": "direct"},
        ip_address=ip_address,
    )
    db.commit()
    return conversation


def _add_initial_members(
    db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID, actor_user_id: uuid.UUID, member_user_ids: list[uuid.UUID]
) -> None:
    # dict.fromkeys(), not a set: dedupes while preserving the caller's
    # order, which matters here -- joined_at (derived from this insertion
    # order) drives auto-promotion's "earliest-joined" tiebreak on leave.
    unique_others = list(dict.fromkeys(uid for uid in member_user_ids if uid != actor_user_id))
    total_size = 1 + len(unique_others)
    if total_size > settings.collaboration_group_max_members:
        raise GroupSizeLimitExceededError(
            f"A group cannot have more than {settings.collaboration_group_max_members} members."
        )
    for user_id in unique_others:
        if not _is_company_member(db, company_id=company_id, user_id=user_id):
            raise NotConversationMemberError("One or more selected users are not members of your company.")

    repository.add_active_member(db, company_id=company_id, conversation_id=conversation_id, user_id=actor_user_id)
    repository.add_member(db, company_id=company_id, conversation_id=conversation_id, user_id=actor_user_id, role="owner")
    for user_id in unique_others:
        repository.add_active_member(db, company_id=company_id, conversation_id=conversation_id, user_id=user_id)
        repository.add_member(db, company_id=company_id, conversation_id=conversation_id, user_id=user_id, role="member")


def create_group_conversation(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    name: str,
    description: str | None,
    member_user_ids: list[uuid.UUID],
    ip_address: str | None,
) -> Conversation:
    name = name.strip()
    if not name:
        raise InvalidConversationTypeError("A group conversation needs a name.")

    conversation = repository.create_conversation(
        db, id=uuid.uuid4(), company_id=company_id, type="group", name=name, description=description,
        project_id=None, created_by=actor_user_id,
    )
    _add_initial_members(
        db, company_id=company_id, conversation_id=conversation.id, actor_user_id=actor_user_id,
        member_user_ids=member_user_ids,
    )

    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="collaboration.conversation_created",
        resource_type="chat_conversation", resource_id=conversation.id, metadata={"type": "group"},
        ip_address=ip_address,
    )
    db.commit()
    return conversation


def create_project_channel(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    project_id: uuid.UUID,
    name: str,
    description: str | None,
    member_user_ids: list[uuid.UUID],
    ip_address: str | None,
) -> Conversation:
    """Requires the project to exist in the SAME company (via
    projects.service.get_project, company-scoped -- never bypasses tenant
    isolation via the project association) plus explicit initial
    membership at creation time, matching how Projects are already
    company-wide-viewable but a channel is still membership-gated.
    """
    get_project(db, company_id=company_id, project_id=project_id)

    name = name.strip()
    if not name:
        raise InvalidConversationTypeError("A project channel needs a name.")

    conversation = repository.create_conversation(
        db, id=uuid.uuid4(), company_id=company_id, type="project_channel", name=name, description=description,
        project_id=project_id, created_by=actor_user_id,
    )
    _add_initial_members(
        db, company_id=company_id, conversation_id=conversation.id, actor_user_id=actor_user_id,
        member_user_ids=member_user_ids,
    )

    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="collaboration.conversation_created",
        resource_type="chat_conversation", resource_id=conversation.id,
        metadata={"type": "project_channel", "project_id": str(project_id)}, ip_address=ip_address,
    )
    db.commit()
    return conversation


# --- conversation reads / membership ---


def get_conversation(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
    return _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)


def get_message_for_reference(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, message_id: uuid.UUID) -> Message:
    """Public entry point for OTHER modules that need to validate "does
    this message exist and is the caller currently authorized to see
    it" without reaching into this module's private helpers -- used by
    app.modules.tasks.service to re-validate a message-sourced task
    reference at creation time (never trusting a client-supplied
    message_id as its own authorization). Raises MessageNotFoundError
    for a nonexistent, deleted, or not-currently-accessible message --
    same IDOR-safe "not found" for every failure mode as everywhere else.
    """
    message = _get_message_or_404(db, company_id=company_id, message_id=message_id)
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=message.conversation_id)
    if message.deleted_at is not None:
        raise MessageNotFoundError("Message not found.")
    return message


def list_conversations(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, limit: int, cursor: tuple[datetime, uuid.UUID] | None
) -> list[Conversation]:
    return repository.list_conversations_for_user(db, company_id=company_id, user_id=actor_user_id, limit=limit, cursor=cursor)


def list_members(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID) -> list[ConversationMember]:
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    return repository.list_active_members(db, company_id=company_id, conversation_id=conversation_id)


def rename_conversation(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID,
    name: str | None, description: str | None, ip_address: str | None,
) -> Conversation:
    conversation = _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    if conversation.type == "direct":
        raise InvalidConversationTypeError("A direct conversation cannot be renamed.")
    _require_admin(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)

    updated = repository.rename_conversation(db, conversation, name=(name or "").strip() or conversation.name, description=description)
    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="collaboration.conversation_renamed",
        resource_type="chat_conversation", resource_id=conversation.id, metadata=None, ip_address=ip_address,
    )
    db.commit()
    return updated


def add_group_member(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID,
    new_user_id: uuid.UUID, ip_address: str | None,
) -> ConversationMember:
    conversation = _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    if conversation.type == "direct":
        raise InvalidConversationTypeError("Cannot add members to a direct conversation.")
    _require_admin(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)

    if not _is_company_member(db, company_id=company_id, user_id=new_user_id):
        raise NotConversationMemberError("That user is not a member of your company.")

    existing = repository.get_member(db, company_id=company_id, conversation_id=conversation_id, user_id=new_user_id)
    if existing is not None and existing.removed_at is None:
        return existing

    current_size = repository.count_active_members(db, company_id=company_id, conversation_id=conversation_id)
    if current_size + 1 > settings.collaboration_group_max_members:
        raise GroupSizeLimitExceededError(
            f"A group cannot have more than {settings.collaboration_group_max_members} members."
        )

    repository.add_active_member(db, company_id=company_id, conversation_id=conversation_id, user_id=new_user_id)
    if existing is not None:
        existing.removed_at = None
        db.flush()
        member = existing
    else:
        member = repository.add_member(db, company_id=company_id, conversation_id=conversation_id, user_id=new_user_id, role="member")

    repository.create_notification(
        db, id=uuid.uuid4(), company_id=company_id, user_id=new_user_id, type="group_added",
        conversation_id=conversation_id, message_id=None, support_ticket_id=None,
        title="You were added to a conversation", body=conversation.name,
    )
    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="collaboration.member_added",
        resource_type="chat_conversation", resource_id=conversation_id, metadata=None, ip_address=ip_address,
    )
    db.commit()
    return member


def remove_group_member(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID,
    target_user_id: uuid.UUID, ip_address: str | None,
) -> None:
    conversation = _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    if conversation.type == "direct":
        raise InvalidConversationTypeError("Cannot remove members from a direct conversation.")
    _require_admin(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)

    target_member = repository.get_member(db, company_id=company_id, conversation_id=conversation_id, user_id=target_user_id)
    if target_member is None or target_member.removed_at is not None:
        raise NotConversationMemberError("That user is not an active member of this conversation.")

    active_members = repository.list_active_members(db, company_id=company_id, conversation_id=conversation_id)
    remaining = [m for m in active_members if m.user_id != target_user_id]
    if target_member.role in ("owner", "admin") and not any(m.role in ("owner", "admin") for m in remaining):
        raise CannotRemoveLastAdminError("Cannot remove the last owner/admin of a group.")

    # Ordering: roster row updated first (still an active member at this
    # point), active-membership row removed last -- see migration 0017.
    repository.soft_remove_member(db, target_member)
    repository.remove_active_member(
        db, company_id=company_id, conversation_id=conversation_id, user_id=target_user_id, acting_user_id=actor_user_id
    )

    repository.create_notification(
        db, id=uuid.uuid4(), company_id=company_id, user_id=target_user_id, type="group_removed",
        conversation_id=conversation_id, message_id=None, support_ticket_id=None,
        title="You were removed from a conversation", body=conversation.name,
    )
    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="collaboration.member_removed",
        resource_type="chat_conversation", resource_id=conversation_id, metadata=None, ip_address=ip_address,
    )
    db.commit()


def leave_conversation(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID, ip_address: str | None) -> None:
    """See migration 0017's docstring for exactly why this three-step
    ordering (roster update -> optional archive -> active-member removal
    LAST) is required for a self-removal to succeed under Postgres RLS,
    including the last-member-leaves-to-empty case.
    """
    conversation = _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    member = _require_active_member_row(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)

    active_members = repository.list_active_members(db, company_id=company_id, conversation_id=conversation_id)
    remaining = [m for m in active_members if m.user_id != actor_user_id]
    needs_promotion = bool(remaining) and member.role in ("owner", "admin") and not any(m.role in ("owner", "admin") for m in remaining)

    repository.soft_remove_member(db, member)

    if not remaining:
        repository.archive_conversation(db, conversation)
    elif needs_promotion:
        admin_candidates = sorted((m for m in remaining if m.role == "admin"), key=lambda m: m.joined_at)
        promotee = admin_candidates[0] if admin_candidates else min(remaining, key=lambda m: m.joined_at)
        repository.update_member_role(db, promotee, role="owner")

    repository.remove_active_member(
        db, company_id=company_id, conversation_id=conversation_id, user_id=actor_user_id, acting_user_id=actor_user_id
    )

    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="collaboration.member_left",
        resource_type="chat_conversation", resource_id=conversation_id, metadata=None, ip_address=ip_address,
    )
    db.commit()


def update_notification_pref(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID, pref: str, ip_address: str | None
) -> ConversationMember:
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    member = _require_active_member_row(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    updated = repository.update_member_notification_pref(db, member, pref=pref)
    db.commit()
    return updated


def mark_read(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID, message_id: uuid.UUID) -> ConversationMember:
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    member = _require_active_member_row(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    message = _get_message_or_404(db, company_id=company_id, message_id=message_id)
    if message.conversation_id != conversation_id:
        raise MessageNotFoundError("Message not found.")
    updated = repository.update_last_read(db, member, message_id=message_id, read_at=datetime.now(UTC))
    db.commit()
    return updated


def unread_count(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID) -> int:
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    member = _require_active_member_row(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    return repository.unread_count(db, member)


# --- mentions ---


def _resolve_mentions(content: str, active_members: list[ConversationMember], users_by_id: dict[uuid.UUID, User]) -> tuple[set[uuid.UUID], bool]:
    """Resolves ONLY against the conversation's real, currently active
    membership -- never a company-wide user search, so a mention can
    never expose or notify a non-member's identity. @all/@channel expand
    to the real active roster at send time, not a stored/stale list.
    """
    lowered = content.lower()
    mentions_all = any(token in lowered for token in _MENTION_ALL_TOKENS)
    mentioned: set[uuid.UUID] = set()
    for member in active_members:
        user = users_by_id.get(member.user_id)
        if user is None or not user.full_name:
            continue
        token = f"@{user.full_name}".strip().lower()
        if token and token in lowered:
            mentioned.add(member.user_id)
    return mentioned, mentions_all


# --- messages ---


def send_message(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    content: str,
    reply_to_message_id: uuid.UUID | None,
    shared_document_id: uuid.UUID | None,
    ip_address: str | None,
) -> Message:
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)

    if message_send_rate_limiter.is_locked(str(actor_user_id)):
        raise CollaborationRateLimitedError("Too many messages sent recently. Please slow down.")

    content = content.strip()
    if not content:
        raise BlankMessageError("Message must not be blank.")
    if len(content) > settings.collaboration_message_max_length:
        raise MessageTooLongError(f"Message must not exceed {settings.collaboration_message_max_length} characters.")

    if reply_to_message_id is not None:
        parent = repository.get_message_by_id(db, company_id=company_id, message_id=reply_to_message_id)
        if parent is None or parent.conversation_id != conversation_id:
            raise MessageNotFoundError("The message you are replying to was not found.")

    if shared_document_id is not None:
        # Sharer must independently be authorized for the document --
        # never trusted just because they typed an ID. Company-scoped,
        # matching documents' own access model (no per-document ACL
        # beyond company_id in this codebase).
        try:
            get_document(db, company_id=company_id, document_id=shared_document_id)
        except DocumentNotFoundError:
            raise DocumentShareNotAuthorizedError("You are not authorized to share that document.") from None

    message_send_rate_limiter.record_failure(str(actor_user_id))
    message = repository.create_message(
        db, id=uuid.uuid4(), company_id=company_id, conversation_id=conversation_id, sender_id=actor_user_id,
        message_type="text", content=content, reply_to_message_id=reply_to_message_id, shared_document_id=shared_document_id,
    )
    repository.touch_conversation(db, repository.get_conversation_by_id(db, company_id=company_id, conversation_id=conversation_id))

    _notify_for_new_message(db, company_id=company_id, conversation_id=conversation_id, message=message, actor_user_id=actor_user_id)

    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="collaboration.message_sent",
        resource_type="chat_message", resource_id=message.id, metadata={"conversation_id": str(conversation_id)},
        ip_address=ip_address,
    )
    db.commit()
    return message


def _notify_for_new_message(db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID, message: Message, actor_user_id: uuid.UUID) -> None:
    active_members = repository.list_active_members(db, company_id=company_id, conversation_id=conversation_id)
    others = [m for m in active_members if m.user_id != actor_user_id]
    if not others:
        return

    user_ids = [m.user_id for m in others]
    users = db.execute(select(User).where(User.id.in_(user_ids))).scalars()
    users_by_id = {u.id: u for u in users}
    mentioned_ids, mentions_all = _resolve_mentions(message.content, active_members, users_by_id)

    sender = db.get(User, actor_user_id)
    sender_label = (sender.full_name if sender and sender.full_name else "Someone")

    parent_sender_id: uuid.UUID | None = None
    if message.reply_to_message_id is not None:
        parent = repository.get_message_by_id(db, company_id=company_id, message_id=message.reply_to_message_id)
        parent_sender_id = parent.sender_id if parent is not None else None

    for member in others:
        if member.notification_pref == "muted":
            continue
        is_mentioned = mentions_all or member.user_id in mentioned_ids
        is_reply_to_them = parent_sender_id is not None and parent_sender_id == member.user_id
        if member.notification_pref == "mentions" and not is_mentioned:
            continue

        if is_mentioned:
            notif_type, title = "mention", f"{sender_label} mentioned you"
        elif is_reply_to_them:
            notif_type, title = "reply", f"{sender_label} replied to you"
        else:
            notif_type, title = "new_message", f"New message from {sender_label}"

        repository.create_notification(
            db, id=uuid.uuid4(), company_id=company_id, user_id=member.user_id, type=notif_type,
            conversation_id=conversation_id, message_id=message.id, support_ticket_id=None,
            title=title, body=message.content[:200],
        )


def edit_message(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, message_id: uuid.UUID, content: str, ip_address: str | None) -> Message:
    message = _get_message_or_404(db, company_id=company_id, message_id=message_id)
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=message.conversation_id)
    if message.deleted_at is not None:
        raise MessageNotFoundError("Message not found.")
    if message.sender_id != actor_user_id:
        raise CannotEditOthersMessageError("You can only edit your own messages.")

    content = content.strip()
    if not content:
        raise BlankMessageError("Message must not be blank.")
    if len(content) > settings.collaboration_message_max_length:
        raise MessageTooLongError(f"Message must not exceed {settings.collaboration_message_max_length} characters.")

    updated = repository.edit_message(db, message, content=content)
    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="collaboration.message_edited",
        resource_type="chat_message", resource_id=message.id, metadata=None, ip_address=ip_address,
    )
    db.commit()
    return updated


def delete_message(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, message_id: uuid.UUID, ip_address: str | None) -> Message:
    message = _get_message_or_404(db, company_id=company_id, message_id=message_id)
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=message.conversation_id)
    if message.deleted_at is not None:
        return message
    if message.sender_id != actor_user_id:
        raise CannotDeleteOthersMessageError("You can only delete your own messages.")

    updated = repository.soft_delete_message(db, message)
    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="collaboration.message_deleted",
        resource_type="chat_message", resource_id=message.id, metadata=None, ip_address=ip_address,
    )
    db.commit()
    return updated


def list_messages(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID, limit: int, cursor: tuple[datetime, uuid.UUID] | None
) -> list[Message]:
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    return repository.list_messages(db, company_id=company_id, conversation_id=conversation_id, limit=limit, cursor=cursor)


def search_conversation(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID, query: str, limit: int) -> list[Message]:
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    query = query.strip()
    if not query:
        return []
    if len(query) > settings.collaboration_search_query_max_length:
        raise SearchQueryTooLongError(f"Search query must not exceed {settings.collaboration_search_query_max_length} characters.")
    bounded_limit = min(limit, settings.collaboration_search_max_results)
    return repository.search_messages(db, company_id=company_id, conversation_id=conversation_id, query_text=query, limit=bounded_limit)


# --- reactions ---


def add_reaction(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, message_id: uuid.UUID, emoji: str) -> None:
    message = _get_message_or_404(db, company_id=company_id, message_id=message_id)
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=message.conversation_id)
    if emoji not in ALLOWED_REACTIONS:
        raise InvalidReactionEmojiError(f"emoji must be one of {sorted(ALLOWED_REACTIONS)}.")
    existing = repository.list_reactions_for_messages(db, company_id=company_id, message_ids=[message_id]).get(message_id, [])
    if any(r.user_id == actor_user_id and r.emoji == emoji for r in existing):
        return
    repository.add_reaction(db, id=uuid.uuid4(), company_id=company_id, message_id=message_id, user_id=actor_user_id, emoji=emoji)
    db.commit()


def remove_reaction(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, message_id: uuid.UUID, emoji: str) -> None:
    message = _get_message_or_404(db, company_id=company_id, message_id=message_id)
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=message.conversation_id)
    repository.remove_reaction(db, company_id=company_id, message_id=message_id, user_id=actor_user_id, emoji=emoji)
    db.commit()


# --- pinned messages ---


def pin_message(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID, message_id: uuid.UUID, ip_address: str | None) -> None:
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    _require_admin(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    message = _get_message_or_404(db, company_id=company_id, message_id=message_id)
    if message.conversation_id != conversation_id:
        raise MessageNotFoundError("Message not found.")
    if repository.get_pin(db, company_id=company_id, conversation_id=conversation_id, message_id=message_id) is not None:
        return
    repository.pin_message(db, id=uuid.uuid4(), company_id=company_id, conversation_id=conversation_id, message_id=message_id, pinned_by=actor_user_id)
    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="collaboration.message_pinned",
        resource_type="chat_message", resource_id=message_id, metadata=None, ip_address=ip_address,
    )
    db.commit()


def unpin_message(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID, message_id: uuid.UUID, ip_address: str | None) -> None:
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    _require_admin(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    repository.unpin_message(db, company_id=company_id, conversation_id=conversation_id, message_id=message_id)
    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="collaboration.message_unpinned",
        resource_type="chat_message", resource_id=message_id, metadata=None, ip_address=ip_address,
    )
    db.commit()


def list_pinned_messages(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID):
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    return repository.list_pinned_messages(db, company_id=company_id, conversation_id=conversation_id)


# --- attachments ---


def upload_attachment(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    filename: str,
    fileobj,
    duration_seconds: int | None,
    ip_address: str | None,
):
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    message = _get_message_or_404(db, company_id=company_id, message_id=message_id)
    if message.conversation_id != conversation_id or message.sender_id != actor_user_id:
        raise MessageNotFoundError("Message not found.")

    size_bytes, _ = measure_and_checksum(fileobj, max_bytes=settings.collaboration_attachment_max_size_bytes)
    if size_bytes > settings.collaboration_attachment_max_size_bytes:
        raise AttachmentTooLargeError(
            f"Attachment exceeds the maximum allowed size of {settings.collaboration_attachment_max_size_bytes} bytes."
        )
    fileobj.seek(0)
    content_type = detect_and_validate_attachment_type(filename=filename, fileobj=fileobj)

    family = content_type.split("/")[-1]
    if duration_seconds is not None:
        if not content_type.startswith("audio/"):
            raise UnsupportedAttachmentTypeError("A voice note (duration_seconds set) must be an audio file.")
        if duration_seconds > settings.collaboration_voice_note_max_seconds:
            raise VoiceNoteTooLongError(
                f"Voice note exceeds the maximum allowed duration of {settings.collaboration_voice_note_max_seconds} seconds."
            )
        kind = "voice_note"
    elif family in IMAGE_FAMILIES or content_type.startswith("image/"):
        kind = "image"
    else:
        kind = "file"

    attachment_id = uuid.uuid4()
    storage_key = build_chat_attachment_object_key(company_id=company_id, attachment_id=attachment_id)
    provider = get_storage_provider()
    fileobj.seek(0)
    provider.upload(key=storage_key, data=fileobj, content_type=content_type)

    attachment = repository.create_attachment(
        db, id=attachment_id, company_id=company_id, message_id=message_id, kind=kind, file_name=filename,
        file_type=content_type, file_size_bytes=size_bytes, storage_key=storage_key, duration_seconds=duration_seconds,
    )
    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="collaboration.attachment_uploaded",
        resource_type="chat_message_attachment", resource_id=attachment.id,
        metadata={"kind": kind, "size_bytes": size_bytes}, ip_address=ip_address,
    )
    db.commit()
    return attachment


def get_attachment_download_url(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, attachment_id: uuid.UUID) -> str:
    attachment = repository.get_attachment_by_id(db, company_id=company_id, attachment_id=attachment_id)
    if attachment is None:
        raise AttachmentNotFoundError("Attachment not found.")
    message = _get_message_or_404(db, company_id=company_id, message_id=attachment.message_id)
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=message.conversation_id)

    provider = get_storage_provider()
    try:
        return provider.generate_download_url(key=attachment.storage_key)
    except ObjectNotFoundError:
        record_audit_event(
            db, company_id=company_id, actor_user_id=actor_user_id, action="collaboration.attachment_security_failure",
            resource_type="chat_message_attachment", resource_id=attachment.id, metadata={"reason": "object_missing"},
            ip_address=None,
        )
        db.commit()
        raise


def list_conversation_media(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID, kind: str | None, limit: int):
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    return repository.list_attachments_for_conversation(db, company_id=company_id, conversation_id=conversation_id, kind=kind, limit=limit)


# --- notifications ---


def list_notifications(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, unread_only: bool, limit: int):
    bounded = min(limit, settings.collaboration_notification_list_max)
    return repository.list_notifications(db, company_id=company_id, user_id=actor_user_id, unread_only=unread_only, limit=bounded)


def count_unread_notifications(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID) -> int:
    return repository.count_unread_notifications(db, company_id=company_id, user_id=actor_user_id)


def mark_notification_read(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, notification_id: uuid.UUID):
    notification = repository.get_notification(db, company_id=company_id, user_id=actor_user_id, notification_id=notification_id)
    if notification is None:
        raise NotificationNotFoundError("Notification not found.")
    updated = repository.mark_notification_read(db, notification)
    db.commit()
    return updated


def mark_all_notifications_read(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID) -> int:
    count = repository.mark_all_notifications_read(db, company_id=company_id, user_id=actor_user_id)
    db.commit()
    return count


# --- calls ---


def start_call(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID, call_type: str, ip_address: str | None) -> CallSession:
    """Session/authorization bookkeeping only, works for any conversation
    size. The FRONTEND only wires real WebRTC media for a 1:1 (2 active
    member) conversation -- for 3+, the UI surfaces that group calling
    needs additional infrastructure (an SFU media server) rather than
    faking a media connection. See the Step 18 report.
    """
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    existing = repository.get_active_call_session_for_conversation(db, company_id=company_id, conversation_id=conversation_id)
    if existing is not None:
        raise CallAlreadyActiveError("A call is already active in this conversation.")

    session = repository.create_call_session(
        db, id=uuid.uuid4(), company_id=company_id, conversation_id=conversation_id, initiated_by=actor_user_id, call_type=call_type
    )
    active_members = repository.list_active_members(db, company_id=company_id, conversation_id=conversation_id)
    for member in active_members:
        participant = repository.add_call_participant(db, id=uuid.uuid4(), company_id=company_id, call_session_id=session.id, user_id=member.user_id)
        if member.user_id == actor_user_id:
            repository.update_call_participant_status(db, participant, status="joined")

    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="collaboration.call_started",
        resource_type="chat_call_session", resource_id=session.id, metadata={"call_type": call_type}, ip_address=ip_address,
    )
    db.commit()
    return session


def _get_call_session_or_404(db: Session, *, company_id: uuid.UUID, call_session_id: uuid.UUID) -> CallSession:
    session = repository.get_call_session(db, company_id=company_id, call_session_id=call_session_id)
    if session is None:
        raise CallSessionNotFoundError("Call session not found.")
    return session


def get_call_session(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, call_session_id: uuid.UUID) -> CallSession:
    session = _get_call_session_or_404(db, company_id=company_id, call_session_id=call_session_id)
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=session.conversation_id)
    return session


def respond_to_call(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, call_session_id: uuid.UUID, status: str, ip_address: str | None) -> CallSession:
    """status is one of joined/declined/left -- validated by the router's
    schema, not here.
    """
    session = _get_call_session_or_404(db, company_id=company_id, call_session_id=call_session_id)
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=session.conversation_id)
    participant = repository.get_call_participant(db, company_id=company_id, call_session_id=call_session_id, user_id=actor_user_id)
    if participant is None:
        raise NotConversationMemberError("You are not a participant in this call.")

    repository.update_call_participant_status(db, participant, status=status)
    if status == "joined" and session.status == "ringing":
        session = repository.update_call_status(db, session, status="active")
    db.commit()
    return session


def end_call(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, call_session_id: uuid.UUID, ip_address: str | None) -> CallSession:
    session = _get_call_session_or_404(db, company_id=company_id, call_session_id=call_session_id)
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=session.conversation_id)
    updated = repository.update_call_status(db, session, status="ended", ended_reason="ended_by_user")
    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="collaboration.call_ended",
        resource_type="chat_call_session", resource_id=session.id, metadata=None, ip_address=ip_address,
    )
    db.commit()
    return updated


def list_call_participants(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, call_session_id: uuid.UUID):
    session = _get_call_session_or_404(db, company_id=company_id, call_session_id=call_session_id)
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=session.conversation_id)
    return repository.list_call_participants(db, company_id=company_id, call_session_id=call_session_id)


# --- AI collaboration ---


def _build_message_context(db: Session, *, company_id: uuid.UUID, messages: list[Message]) -> list[CollaborationMessageContextItem]:
    """Every ref here maps 1:1 to a real message_id in `_ref_to_message_id`
    populated alongside it -- the caller is the sole authority for
    turning a model-returned ref back into a real message.
    """
    sender_ids = {m.sender_id for m in messages if m.sender_id is not None}
    users_by_id: dict[uuid.UUID, User] = {}
    if sender_ids:
        users_by_id = {u.id: u for u in db.execute(select(User).where(User.id.in_(sender_ids))).scalars()}

    items: list[CollaborationMessageContextItem] = []
    for index, message in enumerate(messages):
        if message.deleted_at is not None:
            continue
        sender = users_by_id.get(message.sender_id) if message.sender_id else None
        label = sender.full_name if sender and sender.full_name else "System"
        items.append(CollaborationMessageContextItem(ref=str(index + 1), sender_label=label, content=message.content))
    return items


def _ref_map(messages: list[Message]) -> dict[str, uuid.UUID]:
    mapping: dict[str, uuid.UUID] = {}
    ref_index = 1
    for message in messages:
        if message.deleted_at is not None:
            continue
        mapping[str(ref_index)] = message.id
        ref_index += 1
    return mapping


def _call_insights(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID, messages: list[Message]):
    if ai_insights_rate_limiter.is_locked(str(actor_user_id)):
        raise CollaborationRateLimitedError("Too many AI requests recently. Please try again shortly.")
    ai_insights_rate_limiter.record_failure(str(actor_user_id))

    context = _build_message_context(db, company_id=company_id, messages=messages)
    provider = get_llm_provider()
    try:
        result = provider.generate_collaboration_insights(CollaborationInsightsRequest(messages=context))
    except (LLMAuthenticationError, LLMConfigurationError, LLMMalformedOutputError, LLMOperationError, LLMUnavailable) as exc:
        raise CollaborationAssistantUnavailableError("The AI assistant is currently unavailable.") from exc

    ref_to_message_id = _ref_map(messages)
    valid_decisions = [d for d in result.decisions if d.source_ref is None or d.source_ref in ref_to_message_id]
    valid_action_items = [a for a in result.action_items if a.source_ref is None or a.source_ref in ref_to_message_id]
    return result, valid_decisions, valid_action_items, ref_to_message_id


def summarize_conversation(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID):
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    messages = repository.list_recent_messages(db, company_id=company_id, conversation_id=conversation_id, max_messages=settings.collaboration_insights_max_messages)
    return _call_insights(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id, messages=messages)


def summarize_unread(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID):
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    member = _require_active_member_row(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    messages = repository.list_unread_messages(
        db, company_id=company_id, conversation_id=conversation_id, since=member.last_read_at,
        max_messages=settings.collaboration_insights_max_messages,
    )
    return _call_insights(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id, messages=messages)


def extract_decisions(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID):
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    messages = repository.list_recent_messages(db, company_id=company_id, conversation_id=conversation_id, max_messages=settings.collaboration_insights_max_messages)
    return _call_insights(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id, messages=messages)


def extract_action_items(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID):
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    messages = repository.list_recent_messages(db, company_id=company_id, conversation_id=conversation_id, max_messages=settings.collaboration_insights_max_messages)
    return _call_insights(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id, messages=messages)


def ask_about_conversation(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID, question: str):
    """Reuses generate_grounded_answer unmodified -- see LLMProvider's
    docstring for why. Serves both "Answer Question About Conversation"
    and "Find Relevant Discussion" (the same grounded-QA shape).
    """
    _require_active_conversation(db, company_id=company_id, actor_user_id=actor_user_id, conversation_id=conversation_id)
    question = question.strip()
    if not question:
        raise BlankMessageError("Question must not be blank.")

    if ai_insights_rate_limiter.is_locked(str(actor_user_id)):
        raise CollaborationRateLimitedError("Too many AI requests recently. Please try again shortly.")
    ai_insights_rate_limiter.record_failure(str(actor_user_id))

    messages = repository.list_recent_messages(db, company_id=company_id, conversation_id=conversation_id, max_messages=settings.collaboration_insights_max_messages)
    context_items = _build_message_context(db, company_id=company_id, messages=messages)
    ref_to_message_id = _ref_map(messages)

    provider = get_llm_provider()
    try:
        result = provider.generate_grounded_answer(
            GroundedAnswerRequest(
                question=question,
                document_context=[DocumentContextItem(ref=item.ref, content=f"[{item.sender_label}] {item.content}") for item in context_items],
            )
        )
    except (LLMAuthenticationError, LLMConfigurationError, LLMMalformedOutputError, LLMOperationError, LLMUnavailable) as exc:
        raise CollaborationAssistantUnavailableError("The AI assistant is currently unavailable.") from exc

    valid_refs = [c.ref for c in result.citations if c.ref in ref_to_message_id]
    sufficient = result.sufficient and bool(valid_refs)
    return result, valid_refs, ref_to_message_id, sufficient

