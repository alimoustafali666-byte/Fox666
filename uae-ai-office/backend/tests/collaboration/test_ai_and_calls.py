"""AI collaboration insights (summarize/decisions/action-items/ask) and
call-session lifecycle tests.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.llm.provider import (
    CollaborationActionItem,
    CollaborationDecision,
    CollaborationInsightsResult,
    GroundedAnswerCitation,
    GroundedAnswerResult,
)
from tests.collaboration.helpers import (
    auth_header,
    create_direct,
    seed_member,
    send_message,
    signup,
)


def test_summarize_conversation_scripted(client: TestClient, db_session: Session, fake_llm_provider) -> None:
    alice_token, alice_claims = signup(client, "ai1@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="ai1b@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)
    msg = send_message(client, alice_token, conv["id"], content="Let's ship the report by Friday")

    fake_llm_provider.enqueue_insights(
        CollaborationInsightsResult(
            summary="The team agreed to ship the report by Friday.",
            decisions=[CollaborationDecision(description="Ship the report by Friday", confirmed=True, source_ref="1")],
            action_items=[
                CollaborationActionItem(description="Prepare the report", possible_assignee=None, due_date="Friday", source_ref="1")
            ],
            model_identifier="fake-llm-v1",
            input_tokens=10,
            output_tokens=10,
        )
    )

    resp = client.post(f"/v1/collaboration/conversations/{conv['id']}/ai/summarize", headers=auth_header(alice_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"] == "The team agreed to ship the report by Friday."
    assert len(body["decisions"]) == 1
    assert body["decisions"][0]["confirmed"] is True
    assert body["decisions"][0]["source_message_id"] == msg["id"]
    assert len(body["action_items"]) == 1
    assert body["action_items"][0]["due_date"] == "Friday"


def test_ai_rejects_fabricated_citation_ref(client: TestClient, db_session: Session, fake_llm_provider) -> None:
    """A decision/action-item citing a ref the model was never given must
    be dropped, never surfaced as if it pointed to a real message.
    """
    alice_token, alice_claims = signup(client, "ai2@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="ai2b@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)
    send_message(client, alice_token, conv["id"], content="short conversation")

    fake_llm_provider.enqueue_insights(
        CollaborationInsightsResult(
            summary="summary",
            decisions=[CollaborationDecision(description="fabricated", confirmed=True, source_ref="999")],
            action_items=[],
            model_identifier="fake-llm-v1",
            input_tokens=1,
            output_tokens=1,
        )
    )
    resp = client.post(f"/v1/collaboration/conversations/{conv['id']}/ai/summarize", headers=auth_header(alice_token))
    assert resp.status_code == 200
    assert resp.json()["decisions"] == []


def test_ask_about_conversation_scripted(client: TestClient, db_session: Session, fake_llm_provider) -> None:
    alice_token, alice_claims = signup(client, "ai3@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="ai3b@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)
    msg = send_message(client, alice_token, conv["id"], content="The deadline is next Monday")

    fake_llm_provider.enqueue(
        GroundedAnswerResult(
            answer="The deadline is next Monday.", sufficient=True, citations=[GroundedAnswerCitation(ref="1")],
            model_identifier="fake-llm-v1", input_tokens=5, output_tokens=5,
        )
    )
    resp = client.post(f"/v1/collaboration/conversations/{conv['id']}/ai/ask", json={"question": "When is the deadline?"}, headers=auth_header(alice_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["sufficient"] is True
    assert body["citations"] == [{"message_id": msg["id"]}]


def test_call_lifecycle_1to1(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "call1@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="call1b@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)

    start_resp = client.post(f"/v1/collaboration/conversations/{conv['id']}/calls", json={"call_type": "voice"}, headers=auth_header(alice_token))
    assert start_resp.status_code == 201
    call = start_resp.json()
    assert call["status"] == "ringing"
    assert call["initiated_by"] == alice_claims["sub"]

    # Cannot start a second call while one is ringing.
    dup_resp = client.post(f"/v1/collaboration/conversations/{conv['id']}/calls", json={"call_type": "voice"}, headers=auth_header(alice_token))
    assert dup_resp.status_code == 409

    respond_resp = client.post(f"/v1/collaboration/calls/{call['id']}/respond", json={"status": "joined"}, headers=auth_header(bob_token))
    assert respond_resp.status_code == 200
    assert respond_resp.json()["status"] == "active"

    end_resp = client.post(f"/v1/collaboration/calls/{call['id']}/end", headers=auth_header(alice_token))
    assert end_resp.status_code == 200
    assert end_resp.json()["status"] == "ended"


def test_get_call_session(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "call3@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="call3b@example.com", role="member")
    _carol_token, _carol_id = seed_member(db_session, company_id=alice_claims["company_id"], email="call3c@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)

    start_resp = client.post(f"/v1/collaboration/conversations/{conv['id']}/calls", json={"call_type": "video"}, headers=auth_header(alice_token))
    call_id = start_resp.json()["id"]

    # Bob (a member) can poll the session state -- e.g. while ringing, to
    # detect a decline/answer the WebRTC signaling channel didn't carry.
    get_resp = client.get(f"/v1/collaboration/calls/{call_id}", headers=auth_header(bob_token))
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "ringing"

    # Carol, not a member of the conversation, cannot.
    denied_resp = client.get(f"/v1/collaboration/calls/{call_id}", headers=auth_header(_carol_token))
    assert denied_resp.status_code == 404


def test_nonmember_cannot_start_or_join_call(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "call2@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="call2b@example.com", role="member")
    _carol_token, _carol_id = seed_member(db_session, company_id=alice_claims["company_id"], email="call2c@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)

    start_resp = client.post(f"/v1/collaboration/conversations/{conv['id']}/calls", json={"call_type": "video"}, headers=auth_header(_carol_token))
    assert start_resp.status_code == 404

    real_start = client.post(f"/v1/collaboration/conversations/{conv['id']}/calls", json={"call_type": "video"}, headers=auth_header(alice_token))
    call_id = real_start.json()["id"]
    # Carol isn't a member of the underlying conversation at all -> same
    # IDOR-consistent 404 as every other non-member endpoint (not 403).
    join_resp = client.post(f"/v1/collaboration/calls/{call_id}/respond", json={"status": "joined"}, headers=auth_header(_carol_token))
    assert join_resp.status_code == 404


def test_group_size_limit_enforced(client: TestClient, db_session: Session, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "collaboration_group_max_members", 2)
    alice_token, alice_claims = signup(client, "gsize@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="gsizeb@example.com", role="member")
    _carol_token, carol_id = seed_member(db_session, company_id=alice_claims["company_id"], email="gsizec@example.com", role="member")

    resp = client.post(
        "/v1/collaboration/conversations/group",
        json={"name": "Too Big", "member_user_ids": [str(bob_id), str(carol_id)]},
        headers=auth_header(alice_token),
    )
    assert resp.status_code == 400

