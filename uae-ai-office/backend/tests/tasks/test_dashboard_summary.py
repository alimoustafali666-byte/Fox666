"""Dashboard summary tiles: real counts derived from the caller's own
tasks, never fabricated metrics.
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.tasks.helpers import auth_header, create_task, signup


def test_dashboard_summary_counts(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "dash1@example.com")
    today = datetime.now(UTC).date().isoformat()
    yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    tomorrow = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()

    create_task(client, token, title="due today", assigned_to=claims["sub"], due_date=today)
    create_task(client, token, title="overdue", assigned_to=claims["sub"], due_date=yesterday)
    create_task(client, token, title="upcoming", assigned_to=claims["sub"], due_date=tomorrow)
    create_task(client, token, title="high priority", assigned_to=claims["sub"], priority="high")
    create_task(client, token, title="urgent", assigned_to=claims["sub"], priority="urgent")

    resp = client.get("/v1/tasks/summary", headers=auth_header(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["due_today"] == 1
    assert body["overdue"] == 1
    assert body["high_priority_open"] == 2
    assert body["my_open_tasks"] == 5


def test_completed_task_excluded_from_overdue(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "dash2@example.com")
    yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    task = create_task(client, token, title="was overdue", assigned_to=claims["sub"], due_date=yesterday)

    client.patch(f"/v1/tasks/{task['id']}", json={"status": "in_progress"}, headers=auth_header(token))
    client.patch(f"/v1/tasks/{task['id']}", json={"status": "completed"}, headers=auth_header(token))

    resp = client.get("/v1/tasks/summary", headers=auth_header(token))
    assert resp.json()["overdue"] == 0


def test_dashboard_summary_scoped_to_caller_only(client: TestClient, db_session: Session) -> None:
    from tests.tasks.helpers import seed_member

    owner_token, claims = signup(client, "dash3@example.com")
    member_token, member_id = seed_member(db_session, company_id=claims["company_id"], email="dash3a@example.com", role="member")
    create_task(client, owner_token, title="owner's task", assigned_to=claims["sub"], priority="urgent")

    resp = client.get("/v1/tasks/summary", headers=auth_header(member_token))
    assert resp.json()["high_priority_open"] == 0
    assert member_id

