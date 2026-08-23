from fastapi.testclient import TestClient

from tests.support.helpers import auth_header, create_ticket, signup


def _audit_actions(client: TestClient, token: str) -> list[dict]:
    response = client.get("/v1/audit-logs", headers=auth_header(token))
    assert response.status_code == 200
    return response.json()["items"]


# 22. support audit events work
def test_ticket_created_emits_audit_event(client: TestClient) -> None:
    token, _ = signup(client, "audit-ticket-created@example.com")

    ticket = create_ticket(client, token, category="documents", priority="high")

    entries = _audit_actions(client, token)
    created_events = [e for e in entries if e["action"] == "support.ticket_created"]
    assert len(created_events) == 1
    metadata = created_events[0]["metadata"]
    assert metadata["category"] == "documents"
    assert metadata["priority"] == "high"
    assert metadata["reference_code"] == ticket["reference_code"]
    # Never the full subject/description -- only IDs/category/status
    # metadata, per the Step 17 audit-safety policy.
    assert "subject" not in metadata
    assert "description" not in metadata


def test_ticket_replied_emits_audit_event(client: TestClient) -> None:
    token, _ = signup(client, "audit-ticket-replied@example.com")
    ticket = create_ticket(client, token)

    client.post(
        f"/v1/support/tickets/{ticket['id']}/comments",
        json={"body": "Some confidential troubleshooting detail."},
        headers=auth_header(token),
    )

    entries = _audit_actions(client, token)
    replied_events = [e for e in entries if e["action"] == "support.ticket_replied"]
    assert len(replied_events) == 1
    assert "body" not in replied_events[0]["metadata"]
    assert "Some confidential" not in str(replied_events[0]["metadata"])


def test_ticket_status_changed_emits_audit_event(client: TestClient) -> None:
    token, _ = signup(client, "audit-ticket-status@example.com")
    ticket = create_ticket(client, token)

    client.patch(
        f"/v1/support/tickets/{ticket['id']}/status",
        json={"status": "closed"},
        headers=auth_header(token),
    )

    entries = _audit_actions(client, token)
    status_events = [e for e in entries if e["action"] == "support.ticket_status_changed"]
    assert len(status_events) == 1
    assert status_events[0]["metadata"] == {"from_status": "open", "to_status": "closed"}


def test_assistant_asked_emits_audit_event(client: TestClient) -> None:
    token, _ = signup(client, "audit-assistant-asked@example.com")

    client.post(
        "/v1/support/assistant/ask",
        json={"question": "How do I create a project?"},
        headers=auth_header(token),
    )

    entries = _audit_actions(client, token)
    asked_events = [e for e in entries if e["action"] == "support.assistant_asked"]
    assert len(asked_events) == 1
    assert "question" not in asked_events[0]["metadata"]

