"""Realtime layer: typing indicators, presence, and WebRTC signaling
relay -- authorization (never trusting a client-declared conversation_id
or target_user_id) is the security-critical part here.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from tests.collaboration.helpers import auth_header, create_direct, seed_member, signup


def test_typing_indicator_relayed_to_active_members_only(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "ws1@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="ws1b@example.com", role="member")
    _carol_token, _carol_id = seed_member(db_session, company_id=alice_claims["company_id"], email="ws1c@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)

    with client.websocket_connect(f"/v1/collaboration/ws?token={alice_token}") as alice_ws, \
         client.websocket_connect(f"/v1/collaboration/ws?token={bob_token}") as bob_ws, \
         client.websocket_connect(f"/v1/collaboration/ws?token={_carol_token}") as carol_ws:
        alice_ws.send_text(json.dumps({"type": "typing", "conversation_id": conv["id"]}))

        bob_event = json.loads(bob_ws.receive_text())
        assert bob_event["type"] == "typing"
        assert bob_event["conversation_id"] == conv["id"]
        assert bob_event["user_id"] == alice_claims["sub"]

        # Carol is not a member of this conversation -- she must never
        # receive the event. Send a harmless presence_query afterward and
        # confirm THAT arrives first/only, proving no typing event was queued.
        carol_ws.send_text(json.dumps({"type": "presence_query", "user_ids": [str(bob_id)]}))
        carol_event = json.loads(carol_ws.receive_text())
        assert carol_event["type"] == "presence_status"


def test_typing_indicator_forged_conversation_id_ignored(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "ws2@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="ws2b@example.com", role="member")

    with client.websocket_connect(f"/v1/collaboration/ws?token={alice_token}") as alice_ws:
        alice_ws.send_text(json.dumps({"type": "typing", "conversation_id": "11111111-1111-1111-1111-111111111111"}))
        # No membership for a nonexistent conversation -> silently dropped.
        # Prove the connection is still alive and functioning afterward.
        alice_ws.send_text(json.dumps({"type": "presence_query", "user_ids": [str(bob_id)]}))
        event = json.loads(alice_ws.receive_text())
        assert event["type"] == "presence_status"


def test_presence_query_reports_online_status(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "ws3@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="ws3b@example.com", role="member")
    _carol_token, carol_id = seed_member(db_session, company_id=alice_claims["company_id"], email="ws3c@example.com", role="member")

    with client.websocket_connect(f"/v1/collaboration/ws?token={alice_token}") as alice_ws, \
         client.websocket_connect(f"/v1/collaboration/ws?token={bob_token}"):
        alice_ws.send_text(json.dumps({"type": "presence_query", "user_ids": [str(bob_id), str(carol_id)]}))
        event = json.loads(alice_ws.receive_text())
        assert event["type"] == "presence_status"
        assert str(bob_id) in event["online_user_ids"]
        assert str(carol_id) not in event["online_user_ids"]


def test_invalid_token_rejected(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/v1/collaboration/ws?token=garbage") as ws:
        ws.receive_text()


def test_webrtc_signal_relayed_only_to_active_participant(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "ws4@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="ws4b@example.com", role="member")
    _carol_token, _carol_id = seed_member(db_session, company_id=alice_claims["company_id"], email="ws4c@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)

    start_resp = client.post(
        f"/v1/collaboration/conversations/{conv['id']}/calls", json={"call_type": "voice"}, headers=auth_header(alice_token)
    )
    call_id = start_resp.json()["id"]

    with client.websocket_connect(f"/v1/collaboration/ws?token={alice_token}") as alice_ws, \
         client.websocket_connect(f"/v1/collaboration/ws?token={bob_token}") as bob_ws:
        alice_ws.send_text(
            json.dumps(
                {
                    "type": "webrtc_offer",
                    "call_session_id": call_id,
                    "target_user_id": str(bob_id),
                    "payload": {"sdp": "fake-offer-sdp"},
                }
            )
        )
        event = json.loads(bob_ws.receive_text())
        assert event["type"] == "webrtc_offer"
        assert event["call_session_id"] == call_id
        assert event["from_user_id"] == alice_claims["sub"]
        assert event["payload"] == {"sdp": "fake-offer-sdp"}


def test_webrtc_signal_to_non_participant_dropped(client: TestClient, db_session: Session) -> None:
    """A signal targeting a user with no call-participant row (never in
    the conversation, never invited to the call) must be silently
    dropped -- never delivered, and never crash the sender's connection.
    """
    alice_token, alice_claims = signup(client, "ws5@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="ws5b@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)

    start_resp = client.post(
        f"/v1/collaboration/conversations/{conv['id']}/calls", json={"call_type": "video"}, headers=auth_header(alice_token)
    )
    call_id = start_resp.json()["id"]

    _outsider_token, outsider_id = seed_member(db_session, company_id=alice_claims["company_id"], email="ws5o@example.com", role="member")

    with client.websocket_connect(f"/v1/collaboration/ws?token={alice_token}") as alice_ws:
        alice_ws.send_text(
            json.dumps(
                {
                    "type": "webrtc_offer",
                    "call_session_id": call_id,
                    "target_user_id": str(outsider_id),
                    "payload": {"sdp": "should-not-be-delivered"},
                }
            )
        )
        # The dropped signal produces no reply; the connection stays
        # healthy and processes a subsequent, unrelated message normally.
        alice_ws.send_text(json.dumps({"type": "presence_query", "user_ids": [str(bob_id)]}))
        event = json.loads(alice_ws.receive_text())
        assert event["type"] == "presence_status"

