import uuid

from fastapi.testclient import TestClient

from tests.conversations.helpers import create_conversation, get_conversation, list_conversations
from tests.documents.helpers import auth_header, seed_member, signup


# 5. creator can create conversation
def test_creator_can_create_conversation(client: TestClient) -> None:
    token, _ = signup(client, "conv-create@example.com")
    conversation = create_conversation(client, token, title="My thread")
    assert conversation["title"] == "My thread"
    assert conversation["created_by"] is not None


def test_conversation_can_be_created_without_a_title(client: TestClient) -> None:
    token, _ = signup(client, "conv-create-notitle@example.com")
    conversation = create_conversation(client, token)
    assert conversation["title"] is None


# 6. creator can read conversation
def test_creator_can_read_own_conversation(client: TestClient) -> None:
    token, _ = signup(client, "conv-read@example.com")
    conversation = create_conversation(client, token, title="Readable")
    response = get_conversation(client, token, conversation["id"])
    assert response.status_code == 200
    assert response.json()["id"] == conversation["id"]


def test_creator_can_list_own_conversations(client: TestClient) -> None:
    token, _ = signup(client, "conv-list@example.com")
    create_conversation(client, token, title="First")
    create_conversation(client, token, title="Second")
    response = list_conversations(client, token)
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


# 7. another company cannot read it
def test_another_company_cannot_read_conversation(client: TestClient) -> None:
    token_a, _ = signup(client, "conv-cross-a@example.com")
    conversation = create_conversation(client, token_a, title="Company A thread")

    token_b, _ = signup(client, "conv-cross-b@example.com")
    response = get_conversation(client, token_b, conversation["id"])
    assert response.status_code == 404


# 8. private-conversation policy enforced (same company, different user)
def test_another_user_in_same_company_cannot_read_conversation(
    client: TestClient, db_session
) -> None:
    token_owner, claims = signup(client, "conv-private-owner@example.com")
    conversation = create_conversation(client, token_owner, title="Private thread")

    other_token = seed_member(
        db_session,
        company_id=uuid.UUID(claims["company_id"]),
        email="conv-private-other@example.com",
        role="member",
    )

    response = get_conversation(client, other_token, conversation["id"])
    assert response.status_code == 404

    list_response = client.get("/v1/conversations", headers=auth_header(other_token))
    assert list_response.status_code == 200
    assert list_response.json()["items"] == []


def test_nonexistent_conversation_returns_404(client: TestClient) -> None:
    token, _ = signup(client, "conv-missing@example.com")
    response = get_conversation(client, token, "00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

