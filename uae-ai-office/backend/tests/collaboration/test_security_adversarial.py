"""Adversarial / security regression tests for Step 18, per the spec's
explicit required-test list: cross-company isolation, forged IDs,
removed-member access loss, nonmember blocking, AI-context leakage,
notification leakage, document-sharing authorization, unsafe-attachment
rejection. RLS is the primary enforcement layer here -- these tests
exercise it through the real HTTP API, exactly as an attacker would.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.collaboration.helpers import (
    auth_header,
    create_direct,
    create_group,
    seed_member,
    send_message,
    signup,
)


def test_cross_company_conversation_is_invisible(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "s1a@example.com", company_name="Company A")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="s1b@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)

    eve_token, _eve_claims = signup(client, "s1e@example.com", company_name="Company B")
    resp = client.get(f"/v1/collaboration/conversations/{conv['id']}", headers=auth_header(eve_token))
    assert resp.status_code == 404

    resp2 = client.get(f"/v1/collaboration/conversations/{conv['id']}/messages", headers=auth_header(eve_token))
    assert resp2.status_code == 404


def test_forged_conversation_id_rejected(client: TestClient, db_session: Session) -> None:
    alice_token, _alice_claims = signup(client, "s2@example.com")
    fake_id = uuid.uuid4()
    resp = client.get(f"/v1/collaboration/conversations/{fake_id}", headers=auth_header(alice_token))
    assert resp.status_code == 404

    resp2 = client.post(f"/v1/collaboration/conversations/{fake_id}/messages", json={"content": "x"}, headers=auth_header(alice_token))
    assert resp2.status_code == 404


def test_non_member_in_same_company_cannot_read_conversation(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "s3@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="s3b@example.com", role="member")
    carol_token, _carol_id = seed_member(db_session, company_id=alice_claims["company_id"], email="s3c@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)

    resp = client.get(f"/v1/collaboration/conversations/{conv['id']}", headers=auth_header(carol_token))
    assert resp.status_code == 404
    resp2 = client.get(f"/v1/collaboration/conversations/{conv['id']}/messages", headers=auth_header(carol_token))
    assert resp2.status_code == 404
    resp3 = client.post(f"/v1/collaboration/conversations/{conv['id']}/messages", json={"content": "eavesdrop"}, headers=auth_header(carol_token))
    assert resp3.status_code == 404


def test_removed_member_loses_access_to_future_and_past_messages(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "s4@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="s4b@example.com", role="member")
    conv = create_group(client, alice_token, name="Removal Test", member_user_ids=[bob_id])
    send_message(client, alice_token, conv["id"], content="before removal")

    remove_resp = client.delete(f"/v1/collaboration/conversations/{conv['id']}/members/{bob_id}", headers=auth_header(alice_token))
    assert remove_resp.status_code == 204

    # Bob can no longer see the conversation, its messages, or its roster.
    assert client.get(f"/v1/collaboration/conversations/{conv['id']}", headers=auth_header(bob_token)).status_code == 404
    assert client.get(f"/v1/collaboration/conversations/{conv['id']}/messages", headers=auth_header(bob_token)).status_code == 404
    assert client.get(f"/v1/collaboration/conversations/{conv['id']}/members", headers=auth_header(bob_token)).status_code == 404

    # A message sent after removal is invisible to Bob too.
    send_message(client, alice_token, conv["id"], content="after removal")
    assert client.get(f"/v1/collaboration/conversations/{conv['id']}/messages", headers=auth_header(bob_token)).status_code == 404


def test_nonmember_cannot_summarize_or_ask_ai(client: TestClient, db_session: Session, fake_llm_provider) -> None:
    alice_token, alice_claims = signup(client, "s5@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="s5b@example.com", role="member")
    carol_token, _carol_id = seed_member(db_session, company_id=alice_claims["company_id"], email="s5c@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)
    send_message(client, alice_token, conv["id"], content="confidential business plan details")

    resp = client.post(f"/v1/collaboration/conversations/{conv['id']}/ai/summarize", headers=auth_header(carol_token))
    assert resp.status_code == 404
    resp2 = client.post(f"/v1/collaboration/conversations/{conv['id']}/ai/ask", json={"question": "what was discussed?"}, headers=auth_header(carol_token))
    assert resp2.status_code == 404

    # Confirm the fake provider was never even invoked for Carol's attempts.
    assert len(fake_llm_provider.insights_calls) == 0
    assert len(fake_llm_provider.calls) == 0


def test_ai_summary_never_leaks_another_conversations_content(client: TestClient, db_session: Session, fake_llm_provider) -> None:
    """The AI permission boundary: summarizing conversation A must only
    ever see conversation A's messages, never conversation B's, even
    though both exist in the same company and the same requesting user
    is a member of both.
    """
    alice_token, alice_claims = signup(client, "s6@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="s6b@example.com", role="member")
    _carol_token, carol_id = seed_member(db_session, company_id=alice_claims["company_id"], email="s6c@example.com", role="member")

    conv_a = create_direct(client, alice_token, bob_id)
    conv_b = create_direct(client, alice_token, carol_id)
    send_message(client, alice_token, conv_a["id"], content="SECRET_A content about conversation A")
    send_message(client, alice_token, conv_b["id"], content="SECRET_B content about conversation B")

    resp = client.post(f"/v1/collaboration/conversations/{conv_a['id']}/ai/summarize", headers=auth_header(alice_token))
    assert resp.status_code == 200

    call = fake_llm_provider.insights_calls[-1]
    all_content = " ".join(m.content for m in call.messages)
    assert "SECRET_A" in all_content
    assert "SECRET_B" not in all_content


def test_mention_cannot_notify_or_expose_non_member(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "s7@example.com", full_name="Alice Prime")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="s7b@example.com", role="member")
    _outsider_token, _outsider_id = seed_member(db_session, company_id=alice_claims["company_id"], email="s7o@example.com", role="member", full_name="Outsider Person")
    conv = create_direct(client, alice_token, bob_id)

    # Mentioning a non-member's name does not create a notification for them.
    send_message(client, alice_token, conv["id"], content="Hey @Outsider Person, are you there?")
    notifs = client.get("/v1/collaboration/notifications", headers=auth_header(_outsider_token)).json()
    assert not any(n["conversation_id"] == conv["id"] for n in notifs["items"])


def test_notification_cannot_leak_across_users(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "s8@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="s8b@example.com", role="member")
    carol_token, _carol_id = seed_member(db_session, company_id=alice_claims["company_id"], email="s8c@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)
    send_message(client, alice_token, conv["id"], content="hi bob")

    bob_notifs = client.get("/v1/collaboration/notifications", headers=auth_header(bob_token)).json()
    assert any(n["conversation_id"] == conv["id"] for n in bob_notifs["items"])

    carol_notifs = client.get("/v1/collaboration/notifications", headers=auth_header(carol_token)).json()
    assert not any(n["conversation_id"] == conv["id"] for n in carol_notifs["items"])


def test_document_share_requires_sender_authorization(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "s9@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="s9b@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)

    fake_document_id = uuid.uuid4()
    resp = client.post(
        f"/v1/collaboration/conversations/{conv['id']}/messages",
        json={"content": "check this doc", "shared_document_id": str(fake_document_id)},
        headers=auth_header(alice_token),
    )
    assert resp.status_code == 403


def test_unsafe_attachment_type_rejected(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "s10@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="s10b@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)
    msg = send_message(client, alice_token, conv["id"], content="see attached")

    exe_bytes = b"MZ" + b"\x00" * 100
    resp = client.post(
        f"/v1/collaboration/messages/{msg['id']}/attachments",
        data={"conversation_id": conv["id"]},
        files={"file": ("virus.exe", exe_bytes, "application/octet-stream")},
        headers=auth_header(alice_token),
    )
    assert resp.status_code == 400

    # Renamed executable pretending to be a PDF -- content sniffing must catch it.
    resp2 = client.post(
        f"/v1/collaboration/messages/{msg['id']}/attachments",
        data={"conversation_id": conv["id"]},
        files={"file": ("fake.pdf", exe_bytes, "application/pdf")},
        headers=auth_header(alice_token),
    )
    assert resp2.status_code == 400

    # SVG explicitly disallowed for chat images.
    svg_bytes = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    resp3 = client.post(
        f"/v1/collaboration/messages/{msg['id']}/attachments",
        data={"conversation_id": conv["id"]},
        files={"file": ("image.svg", svg_bytes, "image/svg+xml")},
        headers=auth_header(alice_token),
    )
    assert resp3.status_code == 400


def test_nonmember_cannot_download_attachment(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "s11@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="s11b@example.com", role="member")
    _carol_token, _carol_id = seed_member(db_session, company_id=alice_claims["company_id"], email="s11c@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)
    msg = send_message(client, alice_token, conv["id"], content="see attached")

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 100
    upload_resp = client.post(
        f"/v1/collaboration/messages/{msg['id']}/attachments",
        data={"conversation_id": conv["id"]},
        files={"file": ("photo.png", png_bytes, "image/png")},
        headers=auth_header(alice_token),
    )
    assert upload_resp.status_code == 201
    attachment_id = upload_resp.json()["id"]

    # Bob (a member) can get a download URL.
    ok_resp = client.get(f"/v1/collaboration/attachments/{attachment_id}/download-url", headers=auth_header(bob_token))
    assert ok_resp.status_code == 200

    # Carol (not a member of this conversation) cannot.
    denied_resp = client.get(f"/v1/collaboration/attachments/{attachment_id}/download-url", headers=auth_header(_carol_token))
    assert denied_resp.status_code == 404


def test_deleted_message_reply_reference_degrades_safely(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "s12@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="s12b@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)
    original = send_message(client, alice_token, conv["id"], content="original")
    reply = send_message(client, bob_token, conv["id"], content="reply", reply_to_message_id=original["id"])

    del_resp = client.delete(f"/v1/collaboration/messages/{original['id']}", headers=auth_header(alice_token))
    assert del_resp.status_code == 200

    messages = client.get(f"/v1/collaboration/conversations/{conv['id']}/messages", headers=auth_header(alice_token)).json()
    reply_row = next(m for m in messages["items"] if m["id"] == reply["id"])
    # The reply itself still exists and still references the (now-deleted) parent id.
    assert reply_row["reply_to_message_id"] == original["id"]
    deleted_row = next(m for m in messages["items"] if m["id"] == original["id"])
    assert deleted_row["deleted_at"] is not None
    assert deleted_row["content"] == ""

