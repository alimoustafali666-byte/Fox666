"""Task notifications reuse Step 18's chat_notifications table (see
migration 0018) -- read authorization is therefore already strictly
recipient-private via that table's own existing RLS policy.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.tasks.helpers import auth_header, create_task, seed_member, signup


def test_task_assigned_notification(client: TestClient, db_session: Session) -> None:
    owner_token, claims = signup(client, "notif1@example.com")
    member_token, member_id = seed_member(db_session, company_id=claims["company_id"], email="notif1a@example.com", role="member")

    task = create_task(client, owner_token, title="Do the thing", assigned_to=str(member_id))

    notifs = client.get("/v1/collaboration/notifications", headers=auth_header(member_token)).json()
    task_notifs = [n for n in notifs["items"] if n["type"] == "task_assigned"]
    assert len(task_notifs) == 1
    assert task_notifs[0]["task_id"] == task["id"]

    # The owner (who assigned it, not the recipient) never gets this
    # notification themselves.
    owner_notifs = client.get("/v1/collaboration/notifications", headers=auth_header(owner_token)).json()
    assert not [n for n in owner_notifs["items"] if n["type"] == "task_assigned"]


def test_task_reassigned_notification(client: TestClient, db_session: Session) -> None:
    owner_token, claims = signup(client, "notif2@example.com")
    _member_a_token, member_a_id = seed_member(db_session, company_id=claims["company_id"], email="notif2a@example.com", role="member")
    member_b_token, member_b_id = seed_member(db_session, company_id=claims["company_id"], email="notif2b@example.com", role="member")

    task = create_task(client, owner_token, title="x", assigned_to=str(member_a_id))
    resp = client.patch(f"/v1/tasks/{task['id']}", json={"assigned_to": str(member_b_id)}, headers=auth_header(owner_token))
    assert resp.status_code == 200

    notifs = client.get("/v1/collaboration/notifications", headers=auth_header(member_b_token)).json()
    assert any(n["type"] == "task_reassigned" for n in notifs["items"])


def test_task_comment_notification_goes_to_assignee_and_creator_not_commenter(client: TestClient, db_session: Session) -> None:
    owner_token, claims = signup(client, "notif3@example.com")
    member_token, member_id = seed_member(db_session, company_id=claims["company_id"], email="notif3a@example.com", role="member")
    task = create_task(client, owner_token, title="x", assigned_to=str(member_id))

    # The assignee comments -- notifies the creator (owner), not themselves.
    client.post(f"/v1/tasks/{task['id']}/comments", json={"body": "on it"}, headers=auth_header(member_token))

    owner_notifs = client.get("/v1/collaboration/notifications", headers=auth_header(owner_token)).json()
    assert any(n["type"] == "task_comment" for n in owner_notifs["items"])

    member_notifs = client.get("/v1/collaboration/notifications", headers=auth_header(member_token)).json()
    assert not [n for n in member_notifs["items"] if n["type"] == "task_comment"]


def test_notification_not_visible_to_unrelated_user(client: TestClient, db_session: Session) -> None:
    owner_token, claims = signup(client, "notif4@example.com")
    _member_token, member_id = seed_member(db_session, company_id=claims["company_id"], email="notif4a@example.com", role="member")
    _outsider_token, _outsider_id = seed_member(db_session, company_id=claims["company_id"], email="notif4b@example.com", role="member")

    create_task(client, owner_token, title="x", assigned_to=str(member_id))

    outsider_notifs = client.get("/v1/collaboration/notifications", headers=auth_header(_outsider_token)).json()
    assert not [n for n in outsider_notifs["items"] if n["type"] == "task_assigned"]

