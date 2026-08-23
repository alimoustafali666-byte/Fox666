"""Basic task CRUD: creation defaults, get/list, status transitions,
completion/reopen bookkeeping.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.tasks.helpers import auth_header, create_project, create_task, signup


def test_create_manual_task_defaults(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "crud1@example.com")
    task = create_task(client, token, title="Draft the proposal")
    assert task["status"] == "todo"
    assert task["priority"] == "normal"
    assert task["source_type"] == "manual"
    assert task["source_id"] is None
    assert task["created_by"] == claims["sub"]
    assert task["assigned_to"] is None
    assert task["completed_at"] is None


def test_create_task_with_project(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "crud2@example.com")
    project = create_project(client, token)
    task = create_task(client, token, title="Order rebar", project_id=project["id"])
    assert task["project_id"] == project["id"]


def test_create_task_forged_project_id_rejected(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "crud3@example.com")
    resp = client.post(
        "/v1/tasks", json={"title": "x", "project_id": "11111111-1111-1111-1111-111111111111"}, headers=auth_header(token)
    )
    assert resp.status_code == 404


def test_get_task(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "crud4@example.com")
    task = create_task(client, token)
    resp = client.get(f"/v1/tasks/{task['id']}", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == task["id"]


def test_get_nonexistent_task_404(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "crud5@example.com")
    resp = client.get("/v1/tasks/11111111-1111-1111-1111-111111111111", headers=auth_header(token))
    assert resp.status_code == 404


def test_list_tasks_pagination_and_filters(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "crud6@example.com")
    for i in range(3):
        create_task(client, token, title=f"Task {i}", priority="high" if i == 0 else "normal")

    resp = client.get("/v1/tasks", headers=auth_header(token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 3

    resp2 = client.get("/v1/tasks", params={"priority": "high"}, headers=auth_header(token))
    assert len(resp2.json()["items"]) == 1

    resp3 = client.get("/v1/tasks", params={"limit": 1}, headers=auth_header(token))
    assert len(resp3.json()["items"]) == 1
    assert resp3.json()["next_cursor"] is not None


def test_valid_status_transitions(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "crud7@example.com")
    task = create_task(client, token)

    resp = client.patch(f"/v1/tasks/{task['id']}", json={"status": "in_progress"}, headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"

    resp2 = client.patch(f"/v1/tasks/{task['id']}", json={"status": "completed"}, headers=auth_header(token))
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "completed"
    assert resp2.json()["completed_at"] is not None

    # Reopen clears completed_at.
    resp3 = client.patch(f"/v1/tasks/{task['id']}", json={"status": "todo"}, headers=auth_header(token))
    assert resp3.status_code == 200
    assert resp3.json()["completed_at"] is None


def test_invalid_status_transition_rejected(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "crud8@example.com")
    task = create_task(client, token)
    # todo -> completed directly is not an allowed transition.
    resp = client.patch(f"/v1/tasks/{task['id']}", json={"status": "completed"}, headers=auth_header(token))
    assert resp.status_code == 400

    # A cancelled task cannot be re-cancelled or completed without first reopening.
    cancel_resp = client.patch(f"/v1/tasks/{task['id']}", json={"status": "cancelled"}, headers=auth_header(token))
    assert cancel_resp.status_code == 200
    resp2 = client.patch(f"/v1/tasks/{task['id']}", json={"status": "completed"}, headers=auth_header(token))
    assert resp2.status_code == 400


def test_blank_title_rejected(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "crud9@example.com")
    resp = client.post("/v1/tasks", json={"title": "   "}, headers=auth_header(token))
    assert resp.status_code == 422


def test_oversized_title_rejected(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "crud10@example.com")
    resp = client.post("/v1/tasks", json={"title": "x" * 400}, headers=auth_header(token))
    assert resp.status_code == 422

