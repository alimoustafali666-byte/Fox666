"""End-to-end tests for conversation creation, membership, and the
leave/archive lifecycle -- including the case that was provably
impossible under the first (array-denormalization) RLS design: the last
active member leaving a conversation to an empty membership set.
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


def test_direct_conversation_create_and_dedupe(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "alice@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="bob@example.com", role="member")

    conv = create_direct(client, alice_token, bob_id)
    assert conv["type"] == "direct"

    # Same pair again -> same conversation, not a duplicate.
    conv2 = create_direct(client, alice_token, bob_id)
    assert conv2["id"] == conv["id"]

    # Bob can also see it and it dedupes from his side too.
    conv3 = create_direct(client, bob_token, alice_claims["sub"])
    assert conv3["id"] == conv["id"]


def test_cannot_dm_self(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "alice2@example.com")
    response = client.post(
        "/v1/collaboration/conversations/direct", json={"other_user_id": alice_claims["sub"]}, headers=auth_header(alice_token)
    )
    assert response.status_code == 400


def test_group_conversation_create_and_roster(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "alice3@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="bob3@example.com", role="member")
    _carol_token, carol_id = seed_member(db_session, company_id=alice_claims["company_id"], email="carol3@example.com", role="member")

    conv = create_group(client, alice_token, name="Project Team", member_user_ids=[bob_id, carol_id])
    assert conv["type"] == "group"

    members = client.get(f"/v1/collaboration/conversations/{conv['id']}/members", headers=auth_header(alice_token)).json()
    assert len(members) == 3
    roles = {str(m["user_id"]): m["role"] for m in members}
    assert roles[alice_claims["sub"]] == "owner"
    assert roles[str(bob_id)] == "member"
    assert roles[str(carol_id)] == "member"


def test_leave_conversation_non_last_member(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "alice4@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="bob4@example.com", role="member")

    conv = create_group(client, alice_token, name="Two Person Group", member_user_ids=[bob_id])
    leave = client.post(f"/v1/collaboration/conversations/{conv['id']}/leave", headers=auth_header(bob_token))
    assert leave.status_code == 204

    # Bob no longer sees it.
    get_resp = client.get(f"/v1/collaboration/conversations/{conv['id']}", headers=auth_header(bob_token))
    assert get_resp.status_code == 404

    # Alice still does.
    get_resp2 = client.get(f"/v1/collaboration/conversations/{conv['id']}", headers=auth_header(alice_token))
    assert get_resp2.status_code == 200
    assert get_resp2.json()["archived_at"] is None


def test_last_member_leaving_archives_conversation(client: TestClient, db_session: Session) -> None:
    """The exact scenario that was provably impossible under the
    array-denormalization RLS design: no current_user value could ever
    satisfy `x = ANY('{}')`. Confirms the final active-members-join-table
    design handles it cleanly end-to-end via the real API.
    """
    alice_token, _alice_claims = signup(client, "alice5@example.com")
    conv = create_group(client, alice_token, name="Solo Group")

    leave = client.post(f"/v1/collaboration/conversations/{conv['id']}/leave", headers=auth_header(alice_token))
    assert leave.status_code == 204

    get_resp = client.get(f"/v1/collaboration/conversations/{conv['id']}", headers=auth_header(alice_token))
    assert get_resp.status_code == 404


def test_owner_auto_promotion_on_leave(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "alice6@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="bob6@example.com", role="member")
    _carol_token, carol_id = seed_member(db_session, company_id=alice_claims["company_id"], email="carol6@example.com", role="member")

    conv = create_group(client, alice_token, name="Promotion Test", member_user_ids=[bob_id, carol_id])
    leave = client.post(f"/v1/collaboration/conversations/{conv['id']}/leave", headers=auth_header(alice_token))
    assert leave.status_code == 204

    members = client.get(f"/v1/collaboration/conversations/{conv['id']}/members", headers=auth_header(bob_token)).json()
    roles = {str(m["user_id"]): m["role"] for m in members}
    # Bob joined before Carol (added in that order at creation) -> promoted.
    assert roles[str(bob_id)] == "owner"
    assert alice_claims["sub"] not in roles


def test_admin_can_add_and_remove_member(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "alice7@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="bob7@example.com", role="member")
    _carol_token, carol_id = seed_member(db_session, company_id=alice_claims["company_id"], email="carol7@example.com", role="member")

    conv = create_group(client, alice_token, name="Add Remove Test")

    add_resp = client.post(
        f"/v1/collaboration/conversations/{conv['id']}/members", json={"user_id": str(bob_id)}, headers=auth_header(alice_token)
    )
    assert add_resp.status_code == 201

    # Bob genuinely gained access (not just a roster row) before removal.
    assert client.get(f"/v1/collaboration/conversations/{conv['id']}", headers=auth_header(bob_token)).status_code == 200

    remove_resp = client.delete(f"/v1/collaboration/conversations/{conv['id']}/members/{bob_id}", headers=auth_header(alice_token))
    assert remove_resp.status_code == 204

    members = client.get(f"/v1/collaboration/conversations/{conv['id']}/members", headers=auth_header(alice_token)).json()
    assert str(bob_id) not in {m["user_id"] for m in members}

    # Bob genuinely lost access too (this is the check that would have
    # caught the RLS peer-DELETE bug found during Step 18 testing: the
    # roster row can look correctly removed from Alice's side while
    # chat_conversation_active_members silently still has Bob's row --
    # this only shows up when checked from Bob's OWN session).
    assert client.get(f"/v1/collaboration/conversations/{conv['id']}", headers=auth_header(bob_token)).status_code == 404

    # A non-admin (carol, never added) cannot add members.
    add_resp2 = client.post(
        f"/v1/collaboration/conversations/{conv['id']}/members", json={"user_id": str(carol_id)}, headers=auth_header(_carol_token)
    )
    assert add_resp2.status_code == 404  # carol isn't even a member -> conversation not found


def test_cannot_remove_last_admin(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "alice8@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="bob8@example.com", role="member")

    conv = create_group(client, alice_token, name="Last Admin Test", member_user_ids=[bob_id])
    # Alice is the only owner/admin; try to remove herself via the admin-removal endpoint (not leave).
    resp = client.delete(f"/v1/collaboration/conversations/{conv['id']}/members/{alice_claims['sub']}", headers=auth_header(alice_token))
    assert resp.status_code == 400


def test_send_and_list_messages(client: TestClient, db_session: Session) -> None:
    alice_token, alice_claims = signup(client, "alice9@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=alice_claims["company_id"], email="bob9@example.com", role="member")

    conv = create_direct(client, alice_token, bob_id)
    send_message(client, alice_token, conv["id"], content="Hi Bob")
    send_message(client, bob_token, conv["id"], content="Hi Alice")

    messages = client.get(f"/v1/collaboration/conversations/{conv['id']}/messages", headers=auth_header(alice_token)).json()
    assert len(messages["items"]) == 2

