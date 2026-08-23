"""Messages: send/edit/delete, mentions, replies, reactions, pins --
including the impersonation-defense checks that were added on top of
plain membership (sender_id/user_id must match the acting session).
"""

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


def test_edit_and_delete_own_message_only(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "m1@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="m1b@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)
    msg = send_message(client, alice_token, conv["id"], content="original")

    # Bob cannot edit Alice's message.
    edit_resp = client.patch(f"/v1/collaboration/messages/{msg['id']}", json={"content": "hacked"}, headers=auth_header(bob_token))
    assert edit_resp.status_code == 403

    # Alice can edit her own.
    edit_resp2 = client.patch(f"/v1/collaboration/messages/{msg['id']}", json={"content": "edited"}, headers=auth_header(alice_token))
    assert edit_resp2.status_code == 200
    assert edit_resp2.json()["content"] == "edited"
    assert edit_resp2.json()["edited_at"] is not None

    # Bob cannot delete Alice's message.
    del_resp = client.delete(f"/v1/collaboration/messages/{msg['id']}", headers=auth_header(bob_token))
    assert del_resp.status_code == 403

    # Alice can delete her own.
    del_resp2 = client.delete(f"/v1/collaboration/messages/{msg['id']}", headers=auth_header(alice_token))
    assert del_resp2.status_code == 200
    assert del_resp2.json()["deleted_at"] is not None


def test_reply_to_message(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "m2@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="m2b@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)
    original = send_message(client, alice_token, conv["id"], content="question?")
    reply = send_message(client, bob_token, conv["id"], content="answer", reply_to_message_id=original["id"])
    assert reply["reply_to_message_id"] == original["id"]


def test_reply_to_message_in_other_conversation_rejected(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "m3@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="m3b@example.com", role="member")
    _carol_token, carol_id = seed_member(db_session, company_id=alice_claims["company_id"], email="m3c@example.com", role="member")
    conv1 = create_direct(client, alice_token, bob_id)
    conv2 = create_direct(client, alice_token, carol_id)
    msg_in_conv1 = send_message(client, alice_token, conv1["id"], content="hi bob")

    resp = client.post(
        f"/v1/collaboration/conversations/{conv2['id']}/messages",
        json={"content": "hi carol", "reply_to_message_id": msg_in_conv1["id"]},
        headers=auth_header(alice_token),
    )
    assert resp.status_code == 404


def test_mention_generates_notification(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "m4@example.com", full_name="Alice Wonderland")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="m4b@example.com", role="member", full_name="Bob Builder")
    conv = create_group(client, alice_token, name="Mentions", member_user_ids=[bob_id])

    send_message(client, alice_token, conv["id"], content="Hey @Bob Builder, check this out")

    notifs = client.get("/v1/collaboration/notifications", headers=auth_header(bob_token)).json()
    assert any(n["type"] == "mention" for n in notifs["items"])


def test_reactions_own_only(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "m5@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="m5b@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)
    msg = send_message(client, alice_token, conv["id"], content="react to this")

    resp = client.post(f"/v1/collaboration/messages/{msg['id']}/reactions", json={"emoji": "thumbsup"}, headers=auth_header(bob_token))
    assert resp.status_code == 204

    messages = client.get(f"/v1/collaboration/conversations/{conv['id']}/messages", headers=auth_header(alice_token)).json()
    target = next(m for m in messages["items"] if m["id"] == msg["id"])
    assert target["reactions"] == [{"emoji": "thumbsup", "user_ids": [str(bob_id)]}]

    # Invalid (non-allowlisted) emoji rejected.
    resp2 = client.post(f"/v1/collaboration/messages/{msg['id']}/reactions", json={"emoji": "not-an-emoji"}, headers=auth_header(bob_token))
    assert resp2.status_code == 422

    # Bob can remove his own reaction.
    resp3 = client.delete(f"/v1/collaboration/messages/{msg['id']}/reactions/thumbsup", headers=auth_header(bob_token))
    assert resp3.status_code == 204


def test_pin_requires_admin(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "m6@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="m6b@example.com", role="member")
    conv = create_group(client, alice_token, name="Pins", member_user_ids=[bob_id])
    msg = send_message(client, alice_token, conv["id"], content="pin me")

    # Bob (plain member, not owner/admin) cannot pin.
    resp = client.post(f"/v1/collaboration/conversations/{conv['id']}/pins/{msg['id']}", headers=auth_header(bob_token))
    assert resp.status_code == 403

    # Alice (owner) can.
    resp2 = client.post(f"/v1/collaboration/conversations/{conv['id']}/pins/{msg['id']}", headers=auth_header(alice_token))
    assert resp2.status_code == 204

    pins = client.get(f"/v1/collaboration/conversations/{conv['id']}/pins", headers=auth_header(alice_token)).json()
    assert len(pins) == 1
    assert pins[0]["message_id"] == msg["id"]


def test_search_within_conversation(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "m7@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="m7b@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)
    send_message(client, alice_token, conv["id"], content="the quarterly budget report is ready")
    send_message(client, bob_token, conv["id"], content="unrelated message about lunch")

    resp = client.post(f"/v1/collaboration/conversations/{conv['id']}/search", json={"query": "budget"}, headers=auth_header(alice_token))
    assert resp.status_code == 200
    results = resp.json()["items"]
    assert len(results) == 1
    assert "budget" in results[0]["content"]


def test_get_message_location(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "loc1@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="loc1b@example.com", role="member")
    _carol_token, _carol_id = seed_member(db_session, company_id=alice_claims["company_id"], email="loc1c@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)
    msg = send_message(client, alice_token, conv["id"], content="hello")

    resp = client.get(f"/v1/collaboration/messages/{msg['id']}/location", headers=auth_header(alice_token))
    assert resp.status_code == 200
    assert resp.json()["conversation_id"] == conv["id"]

    # Bob (a member of this conversation) can resolve it too.
    resp2 = client.get(f"/v1/collaboration/messages/{msg['id']}/location", headers=auth_header(bob_token))
    assert resp2.status_code == 200

    # Carol (not a member) cannot.
    resp3 = client.get(f"/v1/collaboration/messages/{msg['id']}/location", headers=auth_header(_carol_token))
    assert resp3.status_code == 404


def test_voice_note_upload(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "m8@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="m8b@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)
    msg = send_message(client, alice_token, conv["id"], content="voice note incoming")

    webm_bytes = b"\x1a\x45\xdf\xa3" + b"\x00" * 200
    resp = client.post(
        f"/v1/collaboration/messages/{msg['id']}/attachments",
        data={"conversation_id": conv["id"], "duration_seconds": "8"},
        files={"file": ("note.webm", webm_bytes, "audio/webm")},
        headers=auth_header(alice_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "voice_note"
    assert body["duration_seconds"] == 8

    # Bob (a member) can fetch a download URL for it.
    dl_resp = client.get(f"/v1/collaboration/attachments/{body['id']}/download-url", headers=auth_header(bob_token))
    assert dl_resp.status_code == 200


def test_voice_note_duration_on_non_audio_file_rejected(client: TestClient, db_session: Session) -> None:
    """duration_seconds is the client's declaration "this is a voice
    note" -- the server must still verify the bytes are actually audio,
    not just trust the flag (a PDF can't become a voice note just by
    attaching a duration).
    """
    alice_token, alice_claims = signup(client, "m9@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="m9b@example.com", role="member")
    conv = create_direct(client, alice_token, bob_id)
    msg = send_message(client, alice_token, conv["id"], content="not actually audio")

    pdf_bytes = b"%PDF-1.4" + b"\x00" * 100
    resp = client.post(
        f"/v1/collaboration/messages/{msg['id']}/attachments",
        data={"conversation_id": conv["id"], "duration_seconds": "5"},
        files={"file": ("note.pdf", pdf_bytes, "application/pdf")},
        headers=auth_header(alice_token),
    )
    assert resp.status_code == 400

