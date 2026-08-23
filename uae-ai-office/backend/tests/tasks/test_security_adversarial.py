"""Adversarial security checks: cross-tenant isolation, forged IDs,
unauthorized assignment/status changes, and injection-safety of
free-text fields.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.tasks.helpers import auth_header, create_task, seed_member, signup


def test_cross_company_task_invisible(client: TestClient, db_session: Session) -> None:
    token_a, _claims_a = signup(client, "adv1a@example.com")
    task = create_task(client, token_a, title="Company A's task")

    token_b, _claims_b = signup(client, "adv1b@example.com", company_name="Other Co")
    resp = client.get(f"/v1/tasks/{task['id']}", headers=auth_header(token_b))
    assert resp.status_code == 404

    list_resp = client.get("/v1/tasks", headers=auth_header(token_b))
    assert task["id"] not in [t["id"] for t in list_resp.json()["items"]]


def test_cross_company_forged_update_rejected(client: TestClient, db_session: Session) -> None:
    token_a, _claims_a = signup(client, "adv2a@example.com")
    task = create_task(client, token_a, title="Company A's task")

    token_b, _claims_b = signup(client, "adv2b@example.com", company_name="Other Co")
    resp = client.patch(f"/v1/tasks/{task['id']}", json={"status": "in_progress"}, headers=auth_header(token_b))
    assert resp.status_code == 404


def test_forged_task_id_everywhere(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "adv3@example.com")
    fake_id = "11111111-1111-1111-1111-111111111111"
    assert client.get(f"/v1/tasks/{fake_id}", headers=auth_header(token)).status_code == 404
    assert client.patch(f"/v1/tasks/{fake_id}", json={"status": "in_progress"}, headers=auth_header(token)).status_code == 404
    assert client.get(f"/v1/tasks/{fake_id}/comments", headers=auth_header(token)).status_code == 404
    assert client.post(f"/v1/tasks/{fake_id}/comments", json={"body": "x"}, headers=auth_header(token)).status_code == 404
    assert client.get(f"/v1/tasks/{fake_id}/activity", headers=auth_header(token)).status_code == 404


def test_forged_assignee_id_rejected(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "adv4@example.com")
    fake_user_id = "11111111-1111-1111-1111-111111111111"
    resp = client.post("/v1/tasks", json={"title": "x", "assigned_to": fake_user_id}, headers=auth_header(token))
    assert resp.status_code == 400


def test_assignee_from_another_company_rejected(client: TestClient, db_session: Session) -> None:
    token_a, _claims_a = signup(client, "adv5a@example.com")
    _token_b, claims_b = signup(client, "adv5b@example.com", company_name="Other Co")
    resp = client.post("/v1/tasks", json={"title": "x", "assigned_to": claims_b["sub"]}, headers=auth_header(token_a))
    assert resp.status_code == 400


def test_member_cannot_escalate_via_status_field_to_change_others(client: TestClient, db_session: Session) -> None:
    """A member updating only {"status": ...} on someone else's
    unrelated (not-assigned-to-them) task must still be rejected -- the
    field is individually allowed for assignees, but this member is
    neither creator nor assignee.
    """
    owner_token, claims = signup(client, "adv6@example.com")
    member_token, _member_id = seed_member(db_session, company_id=claims["company_id"], email="adv6a@example.com", role="member")
    _other_member_token, other_id = seed_member(db_session, company_id=claims["company_id"], email="adv6b@example.com", role="member")
    task = create_task(client, owner_token, title="x", assigned_to=str(other_id))

    resp = client.patch(f"/v1/tasks/{task['id']}", json={"status": "in_progress"}, headers=auth_header(member_token))
    assert resp.status_code == 404  # not visible at all (not creator/assignee/management, unscoped task)


def test_html_content_in_title_and_comment_stored_as_plain_text(client: TestClient, db_session: Session) -> None:
    """No server-side HTML rendering/escaping is expected or needed --
    this proves the content survives round-trip as inert plain text,
    the same "never interpreted" contract the rest of this app relies on
    (React/the API layer render it as text, never dangerouslySetInnerHTML).
    """
    token, _claims = signup(client, "adv7@example.com")
    payload_str = "<script>alert(1)</script>"
    task = create_task(client, token, title=payload_str)
    assert task["title"] == payload_str

    comment_resp = client.post(f"/v1/tasks/{task['id']}/comments", json={"body": payload_str}, headers=auth_header(token))
    assert comment_resp.json()["body"] == payload_str


def test_oversized_comment_rejected(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "adv8@example.com")
    task = create_task(client, token)
    resp = client.post(f"/v1/tasks/{task['id']}/comments", json={"body": "x" * 5000}, headers=auth_header(token))
    assert resp.status_code == 422


def test_invalid_priority_and_status_rejected(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "adv9@example.com")
    resp = client.post("/v1/tasks", json={"title": "x", "priority": "not-a-real-priority"}, headers=auth_header(token))
    assert resp.status_code == 422

    task = create_task(client, token)
    resp2 = client.patch(f"/v1/tasks/{task['id']}", json={"status": "not-a-real-status"}, headers=auth_header(token))
    assert resp2.status_code == 422

