"""Realtime layer for Step 18: typing indicators, presence, and a WebRTC
signaling relay -- multiplexed over ONE WebSocket connection per client,
since all three are small, frequent, latency-sensitive events that don't
belong in Postgres.

ARCHITECTURE / WHY A NATIVE WEBSOCKET, NOT POLLING: uvicorn[standard]
(already a dependency, confirmed via `pip show`) bundles the `websockets`
library, so FastAPI/Starlette's native WebSocket support is available
with ZERO new dependencies -- this is genuine push-based realtime, not
short-interval polling.

DOCUMENTED LIMITATION (same shape as
app.modules.auth.rate_limit.InMemoryLoginRateLimiter): the connection
registry below lives in this ONE process's memory. In a horizontally-
scaled deployment (multiple backend replicas), a user connected to
replica A never receives an event that originates on replica B -- typing
indicators, presence, and signaling would only work for participants
whose connections happen to land on the same instance. Fixing this for
production requires a shared pub/sub layer (Redis Pub/Sub, most
commonly) behind the same broadcast/relay interface, not a rewrite of
the message handlers. Documented and accepted here as the same tradeoff
already made (and disclosed) for the login rate limiter, not a new one.

EPHEMERAL BY DESIGN: nothing in this module is written to Postgres and
nothing is audited. Typing state, presence, and signaling payloads are
transient by nature (see the spec's explicit "NOT persisted... NOT
audited" requirement for typing indicators) -- nothing here needs a
historical record, and persisting it would violate that requirement for
no benefit.

AUTHORIZATION: every inbound event is re-validated against real,
current membership before being relayed -- never trusts a client-
declared conversation_id/call_session_id/target_user_id. A short-lived
DB session (opened, used, and closed per event -- never held open for
the WebSocket's whole lifetime, which could otherwise exhaust the pool
with many concurrent connections) performs the same
membership/participant checks the REST endpoints use.
"""

import json
import uuid
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import SessionLocal, set_company_context, set_user_context
from app.modules.auth.models import User
from app.modules.auth.repository import get_membership
from app.modules.collaboration.models import CallParticipant, CallSession, ConversationMember
from app.modules.collaboration.repository import list_active_members

# user_id -> set of live connections for that user (a user may have
# several tabs/devices open at once, each its own WebSocket).
_connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)


@contextmanager
def _short_lived_session() -> Iterator[Session]:
    """A fresh, standalone session per authorization check -- never held
    open for the WebSocket's whole lifetime (which could otherwise
    exhaust the pool with many concurrent connections). Overridden in
    tests (see tests/collaboration/conftest.py) to yield the test's own
    transaction-scoped session instead of opening a real second
    connection, which would not see that transaction's uncommitted data
    -- the exact same reason app.db.session.get_db is overridden for
    FastAPI's regular HTTP dependency injection in tests.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()

_MAX_MESSAGE_BYTES = 4096
_INBOUND_TYPES = {"typing", "stop_typing", "presence_query", "webrtc_offer", "webrtc_answer", "webrtc_ice_candidate"}
_WEBRTC_SIGNAL_TYPES = {"webrtc_offer", "webrtc_answer", "webrtc_ice_candidate"}


class _AuthFailure(Exception):
    pass


def _authenticate(token: str | None) -> tuple[uuid.UUID, uuid.UUID]:
    """Returns (user_id, company_id). Raises _AuthFailure on any problem
    -- an invalid/expired token, or a token whose claimed company
    membership no longer holds (re-verified against the database, same
    "never trust the JWT's claim alone" rule as get_tenant_context).
    """
    if not token:
        raise _AuthFailure("missing token")
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
        company_id = uuid.UUID(payload["company_id"])
    except (InvalidTokenError, KeyError, ValueError) as exc:
        raise _AuthFailure("invalid token") from exc

    with _short_lived_session() as db:
        set_company_context(db, company_id)
        set_user_context(db, user_id)
        if get_membership(db, user_id, company_id) is None:
            raise _AuthFailure("not a company member")
        if db.get(User, user_id) is None:
            raise _AuthFailure("user not found")
    return user_id, company_id


def _is_active_conversation_member(company_id: uuid.UUID, user_id: uuid.UUID, conversation_id: uuid.UUID) -> bool:
    with _short_lived_session() as db:
        set_company_context(db, company_id)
        set_user_context(db, user_id)
        member = db.execute(
            select(ConversationMember.id).where(
                ConversationMember.company_id == company_id,
                ConversationMember.conversation_id == conversation_id,
                ConversationMember.user_id == user_id,
                ConversationMember.removed_at.is_(None),
            )
        ).scalar_one_or_none()
        return member is not None


def _active_conversation_member_ids(company_id: uuid.UUID, user_id: uuid.UUID, conversation_id: uuid.UUID) -> list[uuid.UUID]:
    """Only ever called after _is_active_conversation_member has already
    confirmed `user_id` belongs, so the roster read below is itself
    RLS-authorized for this session.
    """
    with _short_lived_session() as db:
        set_company_context(db, company_id)
        set_user_context(db, user_id)
        members = list_active_members(db, company_id=company_id, conversation_id=conversation_id)
        return [m.user_id for m in members]


def _is_active_call_participant(company_id: uuid.UUID, user_id: uuid.UUID, call_session_id: uuid.UUID) -> bool:
    with _short_lived_session() as db:
        set_company_context(db, company_id)
        set_user_context(db, user_id)
        session = db.get(CallSession, call_session_id)
        if session is None or session.company_id != company_id:
            return False
        participant = db.execute(
            select(CallParticipant.id).where(
                CallParticipant.company_id == company_id,
                CallParticipant.call_session_id == call_session_id,
                CallParticipant.user_id == user_id,
            )
        ).scalar_one_or_none()
        return participant is not None


async def _send(ws: WebSocket, payload: dict) -> None:
    # Best-effort broadcast to a peer connection: a send failure here
    # means THAT recipient's socket is already dead/dying (a race with
    # their own disconnect), not a problem with the current event being
    # handled -- the affected connection's own receive loop is
    # responsible for its cleanup, not this helper. Deliberately broad:
    # Starlette can raise more than one exception shape depending on the
    # exact point of failure (already-closed socket, ASGI-layer runtime
    # errors), and none of them should ever propagate into the caller's
    # otherwise-unrelated event handling.
    try:
        await ws.send_text(json.dumps(payload))
    except Exception:  # noqa: BLE001, S110
        pass


async def _broadcast_to_user(user_id: uuid.UUID, payload: dict) -> None:
    for ws in list(_connections.get(user_id, ())):
        await _send(ws, payload)


async def handle_connection(websocket: WebSocket, token: str | None) -> None:
    try:
        user_id, company_id = _authenticate(token)
    except _AuthFailure:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    _connections[user_id].add(websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            if len(raw) > _MAX_MESSAGE_BYTES:
                await _send(websocket, {"type": "error", "message": "message too large"})
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await _send(websocket, {"type": "error", "message": "invalid JSON"})
                continue
            if not isinstance(data, dict) or data.get("type") not in _INBOUND_TYPES:
                await _send(websocket, {"type": "error", "message": "unknown or missing type"})
                continue

            await _dispatch(user_id, company_id, data)
    except WebSocketDisconnect:
        pass
    finally:
        _connections[user_id].discard(websocket)
        if not _connections[user_id]:
            del _connections[user_id]


async def _dispatch(user_id: uuid.UUID, company_id: uuid.UUID, data: dict) -> None:
    msg_type = data["type"]

    if msg_type in ("typing", "stop_typing"):
        conversation_id = _parse_uuid(data.get("conversation_id"))
        if conversation_id is None or not _is_active_conversation_member(company_id, user_id, conversation_id):
            return
        for member_id in _active_conversation_member_ids(company_id, user_id, conversation_id):
            if member_id == user_id:
                continue
            await _broadcast_to_user(
                member_id, {"type": msg_type, "conversation_id": str(conversation_id), "user_id": str(user_id)}
            )
        return

    if msg_type == "presence_query":
        raw_ids = data.get("user_ids")
        if not isinstance(raw_ids, list) or len(raw_ids) > 200:
            return
        queried = [uid for raw in raw_ids if (uid := _parse_uuid(raw)) is not None]
        online = [str(uid) for uid in queried if uid in _connections]
        await _broadcast_to_user(user_id, {"type": "presence_status", "online_user_ids": online})
        return

    if msg_type in _WEBRTC_SIGNAL_TYPES:
        call_session_id = _parse_uuid(data.get("call_session_id"))
        target_user_id = _parse_uuid(data.get("target_user_id"))
        payload = data.get("payload")
        if call_session_id is None or target_user_id is None or not isinstance(payload, dict):
            return
        if not _is_active_call_participant(company_id, user_id, call_session_id):
            return
        if not _is_active_call_participant(company_id, target_user_id, call_session_id):
            return
        await _broadcast_to_user(
            target_user_id,
            {
                "type": msg_type,
                "call_session_id": str(call_session_id),
                "from_user_id": str(user_id),
                "payload": payload,
            },
        )


def _parse_uuid(value: object) -> uuid.UUID | None:
    if not isinstance(value, str):
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None

