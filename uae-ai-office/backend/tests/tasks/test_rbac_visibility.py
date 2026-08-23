"""RBAC and per-row visibility: the approved policy is owner/admin/
manager = full access; member = own-created + assigned + project-scoped
tasks only, and may only progress (change status on) a task assigned to
them by someone else.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.tasks.helpers import auth_header, create_project, create_task, seed_member, signup


def test_member_cannot_see_another_members_personal_task(client: TestClient, db_session: Session) -> None:
    owner_token, claims = signup(client, "rbac1@example.com")
    member_a_token, member_a_id = seed_member(db_session, company_id=claims["company_id"], email="rbac1a@example.com", role="member")
    member_b_token, _member_b_id = seed_member(db_session, company_id=claims["company_id"], email="rbac1b@example.com", role="member")

    task = create_task(client, member_a_token, title="Personal", assigned_to=str(member_a_id))

    resp = client.get(f"/v1/tasks/{task['id']}", headers=auth_header(member_b_token))
    assert resp.status_code == 404

    # It also never shows up in member_b's list.
    list_resp = client.get("/v1/tasks", headers=auth_header(member_b_token))
    assert task["id"] not in [t["id"] for t in list_resp.json()["items"]]

    # But the owner (management role) can see it.
    owner_resp = client.get(f"/v1/tasks/{task['id']}", headers=auth_header(owner_token))
    assert owner_resp.status_code == 200


def test_project_scoped_task_visible_to_all_members(client: TestClient, db_session: Session) -> None:
    owner_token, claims = signup(client, "rbac2@example.com")
    member_token, _member_id = seed_member(db_session, company_id=claims["company_id"], email="rbac2a@example.com", role="member")
    project = create_project(client, owner_token)
    task = create_task(client, owner_token, title="Project task", project_id=project["id"])

    resp = client.get(f"/v1/tasks/{task['id']}", headers=auth_header(member_token))
    assert resp.status_code == 200


def test_member_cannot_assign_task_to_someone_else(client: TestClient, db_session: Session) -> None:
    _owner_token, claims = signup(client, "rbac3@example.com")
    member_token, _member_id = seed_member(db_session, company_id=claims["company_id"], email="rbac3a@example.com", role="member")
    _other_token, other_id = seed_member(db_session, company_id=claims["company_id"], email="rbac3b@example.com", role="member")

    resp = client.post("/v1/tasks", json={"title": "x", "assigned_to": str(other_id)}, headers=auth_header(member_token))
    assert resp.status_code == 400


def test_member_can_self_assign(client: TestClient, db_session: Session) -> None:
    _owner_token, claims = signup(client, "rbac4@example.com")
    member_token, member_id = seed_member(db_session, company_id=claims["company_id"], email="rbac4a@example.com", role="member")
    task = create_task(client, member_token, title="x", assigned_to=str(member_id))
    assert task["assigned_to"] == str(member_id)


def test_manager_can_assign_to_anyone(client: TestClient, db_session: Session) -> None:
    _owner_token, claims = signup(client, "rbac5@example.com")
    manager_token, _manager_id = seed_member(db_session, company_id=claims["company_id"], email="rbac5a@example.com", role="manager")
    _member_token, member_id = seed_member(db_session, company_id=claims["company_id"], email="rbac5b@example.com", role="member")
    task = create_task(client, manager_token, title="x", assigned_to=str(member_id))
    assert task["assigned_to"] == str(member_id)


def test_assignee_can_only_change_status_not_other_fields(client: TestClient, db_session: Session) -> None:
    owner_token, claims = signup(client, "rbac6@example.com")
    member_token, member_id = seed_member(db_session, company_id=claims["company_id"], email="rbac6a@example.com", role="member")
    task = create_task(client, owner_token, title="Assigned to member", assigned_to=str(member_id))

    # Assignee CAN progress status.
    resp = client.patch(f"/v1/tasks/{task['id']}", json={"status": "in_progress"}, headers=auth_header(member_token))
    assert resp.status_code == 200

    # Assignee CANNOT retitle, reprioritize, or reassign.
    for payload in ({"title": "hacked"}, {"priority": "urgent"}, {"assigned_to": None}):
        resp2 = client.patch(f"/v1/tasks/{task['id']}", json=payload, headers=auth_header(member_token))
        assert resp2.status_code == 403, payload


def test_creator_can_fully_edit_own_task(client: TestClient, db_session: Session) -> None:
    _owner_token, claims = signup(client, "rbac7@example.com")
    member_token, _member_id = seed_member(db_session, company_id=claims["company_id"], email="rbac7a@example.com", role="member")
    task = create_task(client, member_token, title="Mine")

    resp = client.patch(f"/v1/tasks/{task['id']}", json={"title": "Mine, edited", "priority": "urgent"}, headers=auth_header(member_token))
    assert resp.status_code == 200
    assert resp.json()["title"] == "Mine, edited"
    assert resp.json()["priority"] == "urgent"


def test_uninvolved_member_cannot_update_project_task(client: TestClient, db_session: Session) -> None:
    owner_token, claims = signup(client, "rbac8@example.com")
    member_token, _member_id = seed_member(db_session, company_id=claims["company_id"], email="rbac8a@example.com", role="member")
    project = create_project(client, owner_token)
    task = create_task(client, owner_token, title="Project task", project_id=project["id"])

    # Visible (project-scoped), but the member is neither creator nor
    # assignee, so no write rights at all.
    resp = client.patch(f"/v1/tasks/{task['id']}", json={"status": "in_progress"}, headers=auth_header(member_token))
    assert resp.status_code == 403


def test_admin_has_full_access(client: TestClient, db_session: Session) -> None:
    _owner_token, claims = signup(client, "rbac9@example.com")
    admin_token, _admin_id = seed_member(db_session, company_id=claims["company_id"], email="rbac9a@example.com", role="admin")
    member_token, member_id = seed_member(db_session, company_id=claims["company_id"], email="rbac9b@example.com", role="member")
    task = create_task(client, member_token, title="Member's task")

    resp = client.patch(f"/v1/tasks/{task['id']}", json={"title": "Admin retitled", "assigned_to": str(member_id)}, headers=auth_header(admin_token))
    assert resp.status_code == 200
    assert resp.json()["title"] == "Admin retitled"

