"""Collaboration / Messages API (Step 18). Every collaboration action is
open to all four company roles (owner/admin/manager/member) -- messaging
is a basic collaboration right, like Ask Your Business and Support,
matching the established pattern in this codebase. Conversation-level
permissions (owner/admin/member of a SPECIFIC conversation) are a
separate, finer-grained concern enforced in service.py -- never confused
with company_role.

Every endpoint resolves company_id from TenantContext, never from client
input; conversation/message/attachment IDs are always re-validated for
membership in service.py before use (never trusted from the URL alone).
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, WebSocket
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError
from app.core.pagination import InvalidCursorError, decode_cursor, encode_cursor
from app.core.request_ip import get_client_ip
from app.db.session import get_db
from app.modules.auth.dependencies import get_tenant_context
from app.modules.auth.models import User
from app.modules.auth.service import TenantContext
from app.modules.collaboration import repository, service
from app.modules.collaboration import ws as collaboration_ws
from app.modules.collaboration.models import Conversation, ConversationMember, Message
from app.modules.collaboration.schemas import (
    AddMemberRequest,
    AiActionItemPublic,
    AiAnswerResponse,
    AiCitation,
    AiDecisionPublic,
    AiInsightsResponse,
    AiQuestionRequest,
    AttachmentPublic,
    CallParticipantPublic,
    CallRespondRequest,
    CallSessionPublic,
    CallStartRequest,
    ConversationMemberPublic,
    ConversationPage,
    ConversationPublic,
    ConversationRenameRequest,
    DirectConversationCreate,
    GroupConversationCreate,
    MarkReadRequest,
    MessageCreate,
    MessageEditRequest,
    MessagePage,
    MessagePublic,
    NotificationPage,
    NotificationPrefUpdate,
    NotificationPublic,
    PinnedMessagePublic,
    ProjectChannelCreate,
    ReactionRequest,
    ReactionSummary,
    SearchRequest,
)

router = APIRouter(prefix="/collaboration", tags=["collaboration"])

DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 100


# --- realtime (typing / presence / WebRTC signaling) ---
# Token passed as a query parameter, not an Authorization header: the
# browser WebSocket API cannot set custom headers on the handshake
# request. See app.modules.collaboration.ws for the full design.


@router.websocket("/ws")
async def collaboration_websocket(websocket: WebSocket, token: str | None = None) -> None:
    await collaboration_ws.handle_connection(websocket, token)


# --- mapping helpers ---


def _conversation_to_public(conversation: Conversation, unread: int) -> ConversationPublic:
    return ConversationPublic(
        id=conversation.id, company_id=conversation.company_id, type=conversation.type, name=conversation.name,
        description=conversation.description, project_id=conversation.project_id, created_by=conversation.created_by,
        created_at=conversation.created_at, updated_at=conversation.updated_at, archived_at=conversation.archived_at,
        unread_count=unread,
    )


def _member_to_public(member: ConversationMember, user: User | None) -> ConversationMemberPublic:
    return ConversationMemberPublic(
        user_id=member.user_id, full_name=user.full_name if user else None, role=member.role,
        notification_pref=member.notification_pref, joined_at=member.joined_at, last_read_at=member.last_read_at,
    )


def _message_to_public(
    message: Message, sender_name: str | None, attachments: list, reactions_by_emoji: dict[str, list[uuid.UUID]]
) -> MessagePublic:
    return MessagePublic(
        id=message.id, conversation_id=message.conversation_id, sender_id=message.sender_id, sender_name=sender_name,
        message_type=message.message_type, content=message.content, reply_to_message_id=message.reply_to_message_id,
        shared_document_id=message.shared_document_id, edited_at=message.edited_at, deleted_at=message.deleted_at,
        created_at=message.created_at,
        attachments=[
            AttachmentPublic(
                id=a.id, kind=a.kind, file_name=a.file_name, file_type=a.file_type, file_size_bytes=a.file_size_bytes,
                duration_seconds=a.duration_seconds, created_at=a.created_at,
            )
            for a in attachments
        ],
        reactions=[ReactionSummary(emoji=emoji, user_ids=user_ids) for emoji, user_ids in reactions_by_emoji.items()],
    )


def _load_message_extras(db: Session, *, company_id: uuid.UUID, messages: list[Message]) -> list[MessagePublic]:
    message_ids = [m.id for m in messages]
    sender_ids = {m.sender_id for m in messages if m.sender_id is not None}
    users_by_id: dict[uuid.UUID, User] = {}
    if sender_ids:
        users_by_id = {u.id: u for u in db.execute(select(User).where(User.id.in_(sender_ids))).scalars()}
    attachments_by_message = repository.list_attachments_for_messages(db, company_id=company_id, message_ids=message_ids)
    reactions_by_message = repository.list_reactions_for_messages(db, company_id=company_id, message_ids=message_ids)

    results = []
    for message in messages:
        sender_name = users_by_id.get(message.sender_id).full_name if message.sender_id and message.sender_id in users_by_id else None
        reactions = reactions_by_message.get(message.id, [])
        by_emoji: dict[str, list[uuid.UUID]] = {}
        for r in reactions:
            by_emoji.setdefault(r.emoji, []).append(r.user_id)
        results.append(
            _message_to_public(message, sender_name, attachments_by_message.get(message.id, []), by_emoji)
        )
    return results


def _call_to_public(session, participants) -> CallSessionPublic:
    return CallSessionPublic(
        id=session.id, conversation_id=session.conversation_id, initiated_by=session.initiated_by,
        call_type=session.call_type, status=session.status, started_at=session.started_at, ended_at=session.ended_at,
        ended_reason=session.ended_reason,
        participants=[
            CallParticipantPublic(user_id=p.user_id, status=p.status, joined_at=p.joined_at, left_at=p.left_at)
            for p in participants
        ],
    )


def _decode_cursor_param(cursor: str | None):
    if cursor is None:
        return None
    try:
        return decode_cursor(cursor)
    except InvalidCursorError:
        raise BadRequestError("Invalid pagination cursor.") from None


# --- conversations ---


@router.post("/conversations/direct", response_model=ConversationPublic, status_code=201)
def create_direct_conversation(
    data: DirectConversationCreate, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> ConversationPublic:
    conversation = service.create_direct_conversation(
        db, company_id=context.company_id, actor_user_id=context.user.id, other_user_id=data.other_user_id,
        ip_address=get_client_ip(request),
    )
    return _conversation_to_public(conversation, 0)


@router.post("/conversations/group", response_model=ConversationPublic, status_code=201)
def create_group_conversation(
    data: GroupConversationCreate, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> ConversationPublic:
    conversation = service.create_group_conversation(
        db, company_id=context.company_id, actor_user_id=context.user.id, name=data.name, description=data.description,
        member_user_ids=data.member_user_ids, ip_address=get_client_ip(request),
    )
    return _conversation_to_public(conversation, 0)


@router.post("/conversations/project-channel", response_model=ConversationPublic, status_code=201)
def create_project_channel(
    data: ProjectChannelCreate, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> ConversationPublic:
    conversation = service.create_project_channel(
        db, company_id=context.company_id, actor_user_id=context.user.id, project_id=data.project_id, name=data.name,
        description=data.description, member_user_ids=data.member_user_ids, ip_address=get_client_ip(request),
    )
    return _conversation_to_public(conversation, 0)


@router.get("/conversations", response_model=ConversationPage)
def list_conversations(
    cursor: str | None = None, limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> ConversationPage:
    decoded_cursor = _decode_cursor_param(cursor)
    rows = service.list_conversations(
        db, company_id=context.company_id, actor_user_id=context.user.id, limit=limit + 1, cursor=decoded_cursor
    )
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = encode_cursor(page_rows[-1].updated_at, page_rows[-1].id) if has_more and page_rows else None

    members_by_conv = repository.get_members_for_conversations(
        db, company_id=context.company_id, user_id=context.user.id, conversation_ids=[c.id for c in page_rows]
    )
    items = []
    for conversation in page_rows:
        member = members_by_conv.get(conversation.id)
        unread = repository.unread_count(db, member) if member else 0
        items.append(_conversation_to_public(conversation, unread))
    return ConversationPage(items=items, next_cursor=next_cursor)


@router.get("/conversations/{conversation_id}", response_model=ConversationPublic)
def get_conversation(
    conversation_id: uuid.UUID, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> ConversationPublic:
    conversation = service.get_conversation(db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id)
    unread = service.unread_count(db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id)
    return _conversation_to_public(conversation, unread)


@router.patch("/conversations/{conversation_id}", response_model=ConversationPublic)
def rename_conversation(
    conversation_id: uuid.UUID, data: ConversationRenameRequest, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> ConversationPublic:
    conversation = service.rename_conversation(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id,
        name=data.name, description=data.description, ip_address=get_client_ip(request),
    )
    return _conversation_to_public(conversation, 0)


@router.get("/conversations/{conversation_id}/members", response_model=list[ConversationMemberPublic])
def list_members(
    conversation_id: uuid.UUID, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> list[ConversationMemberPublic]:
    members = service.list_members(db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id)
    user_ids = [m.user_id for m in members]
    users_by_id = {u.id: u for u in db.execute(select(User).where(User.id.in_(user_ids))).scalars()} if user_ids else {}
    return [_member_to_public(m, users_by_id.get(m.user_id)) for m in members]


@router.post("/conversations/{conversation_id}/members", response_model=ConversationMemberPublic, status_code=201)
def add_member(
    conversation_id: uuid.UUID, data: AddMemberRequest, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> ConversationMemberPublic:
    member = service.add_group_member(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id,
        new_user_id=data.user_id, ip_address=get_client_ip(request),
    )
    user = db.get(User, member.user_id)
    return _member_to_public(member, user)


@router.delete("/conversations/{conversation_id}/members/{user_id}", status_code=204)
def remove_member(
    conversation_id: uuid.UUID, user_id: uuid.UUID, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> None:
    service.remove_group_member(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id,
        target_user_id=user_id, ip_address=get_client_ip(request),
    )


@router.post("/conversations/{conversation_id}/leave", status_code=204)
def leave_conversation(
    conversation_id: uuid.UUID, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> None:
    service.leave_conversation(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id,
        ip_address=get_client_ip(request),
    )


@router.put("/conversations/{conversation_id}/notification-pref", response_model=ConversationMemberPublic)
def update_notification_pref(
    conversation_id: uuid.UUID, data: NotificationPrefUpdate, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> ConversationMemberPublic:
    member = service.update_notification_pref(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id,
        pref=data.pref, ip_address=get_client_ip(request),
    )
    return _member_to_public(member, context.user)


@router.post("/conversations/{conversation_id}/read", status_code=204)
def mark_read(
    conversation_id: uuid.UUID, data: MarkReadRequest,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> None:
    service.mark_read(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id,
        message_id=data.message_id,
    )


# --- messages ---


@router.get("/conversations/{conversation_id}/messages", response_model=MessagePage)
def list_messages(
    conversation_id: uuid.UUID, cursor: str | None = None, limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> MessagePage:
    decoded_cursor = _decode_cursor_param(cursor)
    rows = service.list_messages(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id,
        limit=limit + 1, cursor=decoded_cursor,
    )
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = encode_cursor(page_rows[-1].created_at, page_rows[-1].id) if has_more and page_rows else None
    return MessagePage(items=_load_message_extras(db, company_id=context.company_id, messages=page_rows), next_cursor=next_cursor)


@router.post("/conversations/{conversation_id}/messages", response_model=MessagePublic, status_code=201)
def send_message(
    conversation_id: uuid.UUID, data: MessageCreate, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> MessagePublic:
    message = service.send_message(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id,
        content=data.content, reply_to_message_id=data.reply_to_message_id, shared_document_id=data.shared_document_id,
        ip_address=get_client_ip(request),
    )
    return _load_message_extras(db, company_id=context.company_id, messages=[message])[0]


@router.patch("/messages/{message_id}", response_model=MessagePublic)
def edit_message(
    message_id: uuid.UUID, data: MessageEditRequest, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> MessagePublic:
    message = service.edit_message(
        db, company_id=context.company_id, actor_user_id=context.user.id, message_id=message_id, content=data.content,
        ip_address=get_client_ip(request),
    )
    return _load_message_extras(db, company_id=context.company_id, messages=[message])[0]


@router.delete("/messages/{message_id}", response_model=MessagePublic)
def delete_message(
    message_id: uuid.UUID, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> MessagePublic:
    message = service.delete_message(
        db, company_id=context.company_id, actor_user_id=context.user.id, message_id=message_id,
        ip_address=get_client_ip(request),
    )
    return _load_message_extras(db, company_id=context.company_id, messages=[message])[0]


@router.get("/messages/{message_id}/location")
def get_message_location(
    message_id: uuid.UUID, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> dict[str, str]:
    """Resolves a message_id to its conversation_id, membership-gated the
    same way every other message read is -- used by other modules (Step
    19's Task source-reference "view source" link) that only have a
    message_id and need to build a deep link into Messages without
    themselves knowing the conversation it lives in.
    """
    message = service.get_message_for_reference(
        db, company_id=context.company_id, actor_user_id=context.user.id, message_id=message_id
    )
    return {"conversation_id": str(message.conversation_id)}


@router.post("/conversations/{conversation_id}/search", response_model=MessagePage)
def search_conversation(
    conversation_id: uuid.UUID, data: SearchRequest,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> MessagePage:
    rows = service.search_conversation(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id,
        query=data.query, limit=DEFAULT_PAGE_SIZE,
    )
    return MessagePage(items=_load_message_extras(db, company_id=context.company_id, messages=rows), next_cursor=None)


# --- reactions ---


@router.post("/messages/{message_id}/reactions", status_code=204)
def add_reaction(
    message_id: uuid.UUID, data: ReactionRequest,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> None:
    service.add_reaction(db, company_id=context.company_id, actor_user_id=context.user.id, message_id=message_id, emoji=data.emoji)


@router.delete("/messages/{message_id}/reactions/{emoji}", status_code=204)
def remove_reaction(
    message_id: uuid.UUID, emoji: str,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> None:
    service.remove_reaction(db, company_id=context.company_id, actor_user_id=context.user.id, message_id=message_id, emoji=emoji)


# --- pinned messages ---


@router.post("/conversations/{conversation_id}/pins/{message_id}", status_code=204)
def pin_message(
    conversation_id: uuid.UUID, message_id: uuid.UUID, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> None:
    service.pin_message(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id,
        message_id=message_id, ip_address=get_client_ip(request),
    )


@router.delete("/conversations/{conversation_id}/pins/{message_id}", status_code=204)
def unpin_message(
    conversation_id: uuid.UUID, message_id: uuid.UUID, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> None:
    service.unpin_message(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id,
        message_id=message_id, ip_address=get_client_ip(request),
    )


@router.get("/conversations/{conversation_id}/pins", response_model=list[PinnedMessagePublic])
def list_pins(
    conversation_id: uuid.UUID, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> list[PinnedMessagePublic]:
    pins = service.list_pinned_messages(db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id)
    return [PinnedMessagePublic(message_id=p.message_id, pinned_by=p.pinned_by, pinned_at=p.pinned_at) for p in pins]


# --- attachments ---


@router.post("/messages/{message_id}/attachments", response_model=AttachmentPublic, status_code=201)
def upload_attachment(
    message_id: uuid.UUID, request: Request,
    conversation_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    duration_seconds: int | None = Form(default=None),
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> AttachmentPublic:
    attachment = service.upload_attachment(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id,
        message_id=message_id, filename=file.filename or "attachment", fileobj=file.file,
        duration_seconds=duration_seconds, ip_address=get_client_ip(request),
    )
    return AttachmentPublic(
        id=attachment.id, kind=attachment.kind, file_name=attachment.file_name, file_type=attachment.file_type,
        file_size_bytes=attachment.file_size_bytes, duration_seconds=attachment.duration_seconds,
        created_at=attachment.created_at,
    )


@router.get("/attachments/{attachment_id}/download-url")
def get_attachment_download_url(
    attachment_id: uuid.UUID, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> dict[str, str]:
    url = service.get_attachment_download_url(db, company_id=context.company_id, actor_user_id=context.user.id, attachment_id=attachment_id)
    return {"url": url}


@router.get("/conversations/{conversation_id}/media", response_model=list[AttachmentPublic])
def list_conversation_media(
    conversation_id: uuid.UUID, kind: str | None = None, limit: int = Query(default=50, ge=1, le=200),
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> list[AttachmentPublic]:
    attachments = service.list_conversation_media(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id, kind=kind, limit=limit
    )
    return [
        AttachmentPublic(
            id=a.id, kind=a.kind, file_name=a.file_name, file_type=a.file_type, file_size_bytes=a.file_size_bytes,
            duration_seconds=a.duration_seconds, created_at=a.created_at,
        )
        for a in attachments
    ]


# --- notifications ---


@router.get("/notifications", response_model=NotificationPage)
def list_notifications(
    unread_only: bool = False, limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> NotificationPage:
    notifications = service.list_notifications(db, company_id=context.company_id, actor_user_id=context.user.id, unread_only=unread_only, limit=limit)
    unread = service.count_unread_notifications(db, company_id=context.company_id, actor_user_id=context.user.id)
    return NotificationPage(
        items=[
            NotificationPublic(
                id=n.id, type=n.type, conversation_id=n.conversation_id, message_id=n.message_id,
                support_ticket_id=n.support_ticket_id, task_id=n.task_id, title=n.title, body=n.body,
                read_at=n.read_at, created_at=n.created_at,
            )
            for n in notifications
        ],
        unread_count=unread,
    )


@router.post("/notifications/{notification_id}/read", status_code=204)
def mark_notification_read(
    notification_id: uuid.UUID, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> None:
    service.mark_notification_read(db, company_id=context.company_id, actor_user_id=context.user.id, notification_id=notification_id)


@router.post("/notifications/read-all", status_code=204)
def mark_all_notifications_read(context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> None:
    service.mark_all_notifications_read(db, company_id=context.company_id, actor_user_id=context.user.id)


# --- calls ---


@router.post("/conversations/{conversation_id}/calls", response_model=CallSessionPublic, status_code=201)
def start_call(
    conversation_id: uuid.UUID, data: CallStartRequest, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> CallSessionPublic:
    session = service.start_call(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id,
        call_type=data.call_type, ip_address=get_client_ip(request),
    )
    participants = service.list_call_participants(db, company_id=context.company_id, actor_user_id=context.user.id, call_session_id=session.id)
    return _call_to_public(session, participants)


@router.get("/calls/{call_session_id}", response_model=CallSessionPublic)
def get_call_session(
    call_session_id: uuid.UUID, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> CallSessionPublic:
    session = service.get_call_session(db, company_id=context.company_id, actor_user_id=context.user.id, call_session_id=call_session_id)
    participants = service.list_call_participants(db, company_id=context.company_id, actor_user_id=context.user.id, call_session_id=call_session_id)
    return _call_to_public(session, participants)


@router.post("/calls/{call_session_id}/respond", response_model=CallSessionPublic)
def respond_to_call(
    call_session_id: uuid.UUID, data: CallRespondRequest, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> CallSessionPublic:
    session = service.respond_to_call(
        db, company_id=context.company_id, actor_user_id=context.user.id, call_session_id=call_session_id,
        status=data.status, ip_address=get_client_ip(request),
    )
    participants = service.list_call_participants(db, company_id=context.company_id, actor_user_id=context.user.id, call_session_id=call_session_id)
    return _call_to_public(session, participants)


@router.post("/calls/{call_session_id}/end", response_model=CallSessionPublic)
def end_call(
    call_session_id: uuid.UUID, request: Request,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> CallSessionPublic:
    session = service.end_call(
        db, company_id=context.company_id, actor_user_id=context.user.id, call_session_id=call_session_id,
        ip_address=get_client_ip(request),
    )
    participants = service.list_call_participants(db, company_id=context.company_id, actor_user_id=context.user.id, call_session_id=call_session_id)
    return _call_to_public(session, participants)


@router.get("/calls/{call_session_id}/participants", response_model=list[CallParticipantPublic])
def list_call_participants(
    call_session_id: uuid.UUID, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> list[CallParticipantPublic]:
    participants = service.list_call_participants(db, company_id=context.company_id, actor_user_id=context.user.id, call_session_id=call_session_id)
    return [CallParticipantPublic(user_id=p.user_id, status=p.status, joined_at=p.joined_at, left_at=p.left_at) for p in participants]


# --- AI collaboration ---


def _insights_to_response(result, valid_decisions, valid_action_items, ref_to_message_id) -> AiInsightsResponse:
    return AiInsightsResponse(
        summary=result.summary,
        decisions=[
            AiDecisionPublic(
                description=d.description, confirmed=d.confirmed,
                source_message_id=ref_to_message_id.get(d.source_ref) if d.source_ref else None,
            )
            for d in valid_decisions
        ],
        action_items=[
            AiActionItemPublic(
                description=a.description, possible_assignee=a.possible_assignee, due_date=a.due_date,
                source_message_id=ref_to_message_id.get(a.source_ref) if a.source_ref else None,
            )
            for a in valid_action_items
        ],
    )


@router.post("/conversations/{conversation_id}/ai/summarize", response_model=AiInsightsResponse)
def summarize_conversation(
    conversation_id: uuid.UUID, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> AiInsightsResponse:
    result, decisions, action_items, ref_map = service.summarize_conversation(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id
    )
    return _insights_to_response(result, decisions, action_items, ref_map)


@router.post("/conversations/{conversation_id}/ai/summarize-unread", response_model=AiInsightsResponse)
def summarize_unread(
    conversation_id: uuid.UUID, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> AiInsightsResponse:
    result, decisions, action_items, ref_map = service.summarize_unread(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id
    )
    return _insights_to_response(result, decisions, action_items, ref_map)


@router.post("/conversations/{conversation_id}/ai/decisions", response_model=AiInsightsResponse)
def extract_decisions(
    conversation_id: uuid.UUID, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> AiInsightsResponse:
    result, decisions, action_items, ref_map = service.extract_decisions(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id
    )
    return _insights_to_response(result, decisions, action_items, ref_map)


@router.post("/conversations/{conversation_id}/ai/action-items", response_model=AiInsightsResponse)
def extract_action_items(
    conversation_id: uuid.UUID, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> AiInsightsResponse:
    result, decisions, action_items, ref_map = service.extract_action_items(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id
    )
    return _insights_to_response(result, decisions, action_items, ref_map)


@router.post("/conversations/{conversation_id}/ai/ask", response_model=AiAnswerResponse)
def ask_about_conversation(
    conversation_id: uuid.UUID, data: AiQuestionRequest,
    context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db),
) -> AiAnswerResponse:
    result, valid_refs, ref_map, sufficient = service.ask_about_conversation(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id, question=data.question
    )
    return AiAnswerResponse(
        answer=result.answer, sufficient=sufficient,
        citations=[AiCitation(message_id=ref_map[ref]) for ref in valid_refs],
    )

