import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.support.helpers import auth_header, create_ticket, seed_member, signup


# 7-10. every role can create a ticket
def test_owner_can_create_ticket(client: TestClient) -> None:
    token, _ = signup(client, "ticket-owner@example.com")
    ticket = create_ticket(client, token)
    assert ticket["status"] == "open"
    assert ticket["reference_code"].startswith("REF-")


def test_admin_can_create_ticket(client: TestClient, db_session: Session) -> None:
    _, owner_claims = signup(client, "ticket-admin-owner@example.com")
    admin_token = seed_member(
        db_session,
        company_id=uuid.UUID(owner_claims["company_id"]),
        email="ticket-admin@example.com",
        role="admin",
    )
    create_ticket(client, admin_token)


def test_manager_can_create_ticket(client: TestClient, db_session: Session) -> None:
    _, owner_claims = signup(client, "ticket-manager-owner@example.com")
    manager_token = seed_member(
        db_session,
        company_id=uuid.UUID(owner_claims["company_id"]),
        email="ticket-manager@example.com",
        role="manager",
    )
    create_ticket(client, manager_token)


def test_member_can_create_ticket(client: TestClient, db_session: Session) -> None:
    _, owner_claims = signup(client, "ticket-member-owner@example.com")
    member_token = seed_member(
        db_session,
        company_id=uuid.UUID(owner_claims["company_id"]),
        email="ticket-member@example.com",
        role="member",
    )
    create_ticket(client, member_token)


# 11. creator can view own ticket
def test_creator_can_view_own_ticket(client: TestClient) -> None:
    token, _ = signup(client, "ticket-view-own@example.com")
    ticket = create_ticket(client, token)

    response = client.get(f"/v1/support/tickets/{ticket['id']}", headers=auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == ticket["id"]
    assert body["comments"] == []


# Creator-private: even another member of the SAME company cannot see it.
def test_another_company_member_cannot_view_someone_elses_ticket(
    client: TestClient, db_session: Session
) -> None:
    owner_token, owner_claims = signup(client, "ticket-privacy-owner@example.com")
    ticket = create_ticket(client, owner_token)
    member_token = seed_member(
        db_session,
        company_id=uuid.UUID(owner_claims["company_id"]),
        email="ticket-privacy-member@example.com",
        role="member",
    )

    response = client.get(f"/v1/support/tickets/{ticket['id']}", headers=auth_header(member_token))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "support_ticket_not_found"


# 12. another company cannot view ticket
def test_another_company_cannot_view_ticket(client: TestClient) -> None:
    token_a, _ = signup(client, "ticket-cross-a@example.com", "Company A")
    ticket = create_ticket(client, token_a)
    token_b, _ = signup(client, "ticket-cross-b@example.com", "Company B")

    response = client.get(f"/v1/support/tickets/{ticket['id']}", headers=auth_header(token_b))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "support_ticket_not_found"


# 13. arbitrary ticket ID cannot cause IDOR -- identical 404 to the two
# cases above, never distinguishable from "never existed".
def test_arbitrary_ticket_id_returns_identical_not_found(client: TestClient) -> None:
    token, _ = signup(client, "ticket-idor@example.com")

    response = client.get(f"/v1/support/tickets/{uuid.uuid4()}", headers=auth_header(token))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "support_ticket_not_found"


def test_list_tickets_only_shows_own_tickets(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "ticket-list-owner@example.com")
    create_ticket(client, owner_token, subject="Owner's ticket")
    member_token = seed_member(
        db_session,
        company_id=uuid.UUID(owner_claims["company_id"]),
        email="ticket-list-member@example.com",
        role="member",
    )
    create_ticket(client, member_token, subject="Member's ticket")

    owner_list = client.get("/v1/support/tickets", headers=auth_header(owner_token))
    member_list = client.get("/v1/support/tickets", headers=auth_header(member_token))

    assert owner_list.status_code == 200
    assert member_list.status_code == 200
    assert [t["subject"] for t in owner_list.json()["items"]] == ["Owner's ticket"]
    assert [t["subject"] for t in member_list.json()["items"]] == ["Member's ticket"]


# 14. ticket reply persists
def test_ticket_reply_persists(client: TestClient) -> None:
    token, _ = signup(client, "ticket-reply@example.com")
    ticket = create_ticket(client, token)

    reply = client.post(
        f"/v1/support/tickets/{ticket['id']}/comments",
        json={"body": "Any update on this?"},
        headers=auth_header(token),
    )
    assert reply.status_code == 201
    assert reply.json()["author_type"] == "user"

    detail = client.get(f"/v1/support/tickets/{ticket['id']}", headers=auth_header(token))
    assert detail.status_code == 200
    comments = detail.json()["comments"]
    assert len(comments) == 1
    assert comments[0]["body"] == "Any update on this?"


def test_cannot_reply_to_another_companys_ticket(client: TestClient) -> None:
    token_a, _ = signup(client, "ticket-reply-cross-a@example.com", "Company A")
    ticket = create_ticket(client, token_a)
    token_b, _ = signup(client, "ticket-reply-cross-b@example.com", "Company B")

    response = client.post(
        f"/v1/support/tickets/{ticket['id']}/comments",
        json={"body": "trying to reply cross-tenant"},
        headers=auth_header(token_b),
    )

    assert response.status_code == 404


def test_empty_comment_is_rejected(client: TestClient) -> None:
    token, _ = signup(client, "ticket-empty-comment@example.com")
    ticket = create_ticket(client, token)

    response = client.post(
        f"/v1/support/tickets/{ticket['id']}/comments",
        json={"body": "   "},
        headers=auth_header(token),
    )

    assert response.status_code == 422


def test_comment_over_max_length_is_rejected(client: TestClient) -> None:
    token, _ = signup(client, "ticket-long-comment@example.com")
    ticket = create_ticket(client, token)

    response = client.post(
        f"/v1/support/tickets/{ticket['id']}/comments",
        json={"body": "a" * 10_000},
        headers=auth_header(token),
    )

    assert response.status_code == 422


# 15. status values validated
def test_invalid_status_value_is_rejected(client: TestClient) -> None:
    token, _ = signup(client, "ticket-bad-status@example.com")
    ticket = create_ticket(client, token)

    response = client.patch(
        f"/v1/support/tickets/{ticket['id']}/status",
        json={"status": "deleted_forever"},
        headers=auth_header(token),
    )

    assert response.status_code == 422


def test_creator_can_close_own_ticket(client: TestClient) -> None:
    token, _ = signup(client, "ticket-close@example.com")
    ticket = create_ticket(client, token)

    response = client.patch(
        f"/v1/support/tickets/{ticket['id']}/status",
        json={"status": "closed"},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "closed"


def test_only_closed_transition_is_allowed_in_this_release(client: TestClient) -> None:
    token, _ = signup(client, "ticket-transition@example.com")
    ticket = create_ticket(client, token)

    response = client.patch(
        f"/v1/support/tickets/{ticket['id']}/status",
        json={"status": "resolved"},
        headers=auth_header(token),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_ticket_status_transition"


def test_cannot_close_already_closed_ticket(client: TestClient) -> None:
    token, _ = signup(client, "ticket-double-close@example.com")
    ticket = create_ticket(client, token)
    first = client.patch(
        f"/v1/support/tickets/{ticket['id']}/status",
        json={"status": "closed"},
        headers=auth_header(token),
    )
    assert first.status_code == 200

    second = client.patch(
        f"/v1/support/tickets/{ticket['id']}/status",
        json={"status": "closed"},
        headers=auth_header(token),
    )

    assert second.status_code == 400


# 16. priority values validated
def test_invalid_priority_is_rejected(client: TestClient) -> None:
    token, _ = signup(client, "ticket-bad-priority@example.com")

    response = client.post(
        "/v1/support/tickets",
        json={
            "category": "documents",
            "subject": "Subject",
            "description": "Description",
            "priority": "catastrophic",
        },
        headers=auth_header(token),
    )

    assert response.status_code == 422


def test_invalid_category_is_rejected(client: TestClient) -> None:
    token, _ = signup(client, "ticket-bad-category@example.com")

    response = client.post(
        "/v1/support/tickets",
        json={
            "category": "not_a_real_category",
            "subject": "Subject",
            "description": "Description",
        },
        headers=auth_header(token),
    )

    assert response.status_code == 422


def test_blank_subject_is_rejected(client: TestClient) -> None:
    token, _ = signup(client, "ticket-blank-subject@example.com")

    response = client.post(
        "/v1/support/tickets",
        json={"category": "documents", "subject": "   ", "description": "Description"},
        headers=auth_header(token),
    )

    assert response.status_code == 422


def test_subject_over_max_length_is_rejected(client: TestClient) -> None:
    token, _ = signup(client, "ticket-long-subject@example.com")

    response = client.post(
        "/v1/support/tickets",
        json={"category": "documents", "subject": "a" * 500, "description": "Description"},
        headers=auth_header(token),
    )

    assert response.status_code == 422


def test_description_over_max_length_is_rejected(client: TestClient) -> None:
    token, _ = signup(client, "ticket-long-description@example.com")

    response = client.post(
        "/v1/support/tickets",
        json={"category": "documents", "subject": "Subject", "description": "a" * 20_000},
        headers=auth_header(token),
    )

    assert response.status_code == 422


def test_unauthenticated_cannot_create_ticket(client: TestClient) -> None:
    response = client.post(
        "/v1/support/tickets",
        json={"category": "documents", "subject": "Subject", "description": "Description"},
    )

    assert response.status_code == 401

