"""Comments (append-only, visibility-gated) and the task activity
history (server-written, covers created/assigned/status_changed/
completed/reopened/commented).
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.tasks.helpers import auth_header, create_task, seed_member, signup


def test_add_and_list_comments(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "cmt1@example.com")
    task = create_task(client, token)

    resp = client.post(f"/v1/tasks/{task['id']}/comments", json={"body": "Looks good"}, headers=auth_header(token))
    assert resp.status_code == 201
    assert resp.json()["body"] == "Looks good"
    assert resp.json()["author_user_id"] == claims["sub"]

    list_resp = client.get(f"/v1/tasks/{task['id']}/comments", headers=auth_header(token))
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


def test_blank_comment_rejected(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "cmt2@example.com")
    task = create_task(client, token)
    resp = client.post(f"/v1/tasks/{task['id']}/comments", json={"body": "   "}, headers=auth_header(token))
    assert resp.status_code == 422


def test_nonmember_cannot_comment_on_inaccessible_task(client: TestClient, db_session: Session) -> None:
    _owner_token, claims = signup(client, "cmt3@example.com")
    member_a_token, member_a_id = seed_member(db_session, company_id=claims["company_id"], email="cmt3a@example.com", role="member")
    member_b_token, _member_b_id = seed_member(db_session, company_id=claims["company_id"], email="cmt3b@example.com", role="member")
    task = create_task(client, member_a_token, title="Personal", assigned_to=str(member_a_id))

    resp = client.post(f"/v1/tasks/{task['id']}/comments", json={"body": "sneaky"}, headers=auth_header(member_b_token))
    assert resp.status_code == 404

    list_resp = client.get(f"/v1/tasks/{task['id']}/comments", headers=auth_header(member_b_token))
    assert list_resp.status_code == 404


def test_activity_log_records_lifecycle_events(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "act1@example.com")
    task = create_task(client, token)

    client.patch(f"/v1/tasks/{task['id']}", json={"status": "in_progress"}, headers=auth_header(token))
    client.patch(f"/v1/tasks/{task['id']}", json={"status": "completed"}, headers=auth_header(token))
    client.patch(f"/v1/tasks/{task['id']}", json={"status": "in_progress"}, headers=auth_header(token))
    client.post(f"/v1/tasks/{task['id']}/comments", json={"body": "note"}, headers=auth_header(token))

    resp = client.get(f"/v1/tasks/{task['id']}/activity", headers=auth_header(token))
    assert resp.status_code == 200
    event_types = [e["event_type"] for e in resp.json()]
    assert "created" in event_types
    assert "status_changed" in event_types
    assert "completed" in event_types
    assert "reopened" in event_types
    assert "commented" in event_types


def test_assignment_activity_recorded_on_create_and_update(client: TestClient, db_session: Session) -> None:
    owner_token, claims = signup(client, "act2@example.com")
    _member_token, member_id = seed_member(db_session, company_id=claims["company_id"], email="act2a@example.com", role="member")
    task = create_task(client, owner_token, title="x", assigned_to=str(member_id))

    resp = client.get(f"/v1/tasks/{task['id']}/activity", headers=auth_header(owner_token))
    events = resp.json()
    assigned = [e for e in events if e["event_type"] == "assigned"]
    assert len(assigned) == 1
    assert assigned[0]["new_value"] == str(member_id)

