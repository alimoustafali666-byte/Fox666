import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import set_company_context
from app.modules.projects.models import Project
from tests.projects.helpers import auth_header, seed_member, signup


def _create(client: TestClient, token: str, **kwargs) -> dict:
    payload = {"name": "Project"} | kwargs
    response = client.post("/v1/projects", json=payload, headers=auth_header(token))
    assert response.status_code == 201
    return response.json()


# 29. owner can cancel/delete project
def test_owner_can_delete_project(client: TestClient) -> None:
    token, _ = signup(client, "delete-owner@example.com")
    project = _create(client, token, name="To Cancel")

    response = client.delete(f"/v1/projects/{project['id']}", headers=auth_header(token))

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


# 30. admin can cancel/delete project
def test_admin_can_delete_project(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "delete-admin-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    project = _create(client, owner_token, name="To Cancel")
    admin_token = seed_member(db_session, company_id=company_id, email="delete-admin@example.com", role="admin")

    response = client.delete(f"/v1/projects/{project['id']}", headers=auth_header(admin_token))

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


# 31. manager cannot cancel/delete project
def test_manager_cannot_delete_project(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "delete-manager-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    project = _create(client, owner_token, name="Protected")
    manager_token = seed_member(
        db_session, company_id=company_id, email="delete-manager@example.com", role="manager"
    )

    response = client.delete(f"/v1/projects/{project['id']}", headers=auth_header(manager_token))

    assert response.status_code == 403


# 32. member cannot cancel/delete project
def test_member_cannot_delete_project(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "delete-member-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    project = _create(client, owner_token, name="Protected")
    member_token = seed_member(
        db_session, company_id=company_id, email="delete-member@example.com", role="member"
    )

    response = client.delete(f"/v1/projects/{project['id']}", headers=auth_header(member_token))

    assert response.status_code == 403


# 23. cross-company project ID cannot be deleted
def test_cross_company_project_id_cannot_be_deleted(client: TestClient) -> None:
    token_a, _ = signup(client, "delete-iso-a@example.com", "Company A")
    token_b, _ = signup(client, "delete-iso-b@example.com", "Company B")
    project_b = _create(client, token_b, name="B's Project")

    response = client.delete(f"/v1/projects/{project_b['id']}", headers=auth_header(token_a))

    assert response.status_code == 404


# 33. DELETE transitions status to cancelled without removing row
def test_delete_does_not_remove_the_row(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "delete-no-physical-delete@example.com")
    project = _create(client, token, name="Still Here")

    client.delete(f"/v1/projects/{project['id']}", headers=auth_header(token))

    set_company_context(db_session, uuid.UUID(claims["company_id"]))
    row = db_session.execute(
        select(Project).where(Project.id == uuid.UUID(project["id"]))
    ).scalar_one()

    assert row is not None
    assert row.status == "cancelled"


def test_deleting_an_already_cancelled_project_is_idempotent(client: TestClient) -> None:
    token, _ = signup(client, "delete-idempotent@example.com")
    project = _create(client, token, name="Cancel Twice")

    first = client.delete(f"/v1/projects/{project['id']}", headers=auth_header(token))
    second = client.delete(f"/v1/projects/{project['id']}", headers=auth_header(token))

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "cancelled"


def test_cancelled_project_is_still_gettable(client: TestClient) -> None:
    token, _ = signup(client, "delete-still-gettable@example.com")
    project = _create(client, token, name="Cancel Then Get")

    client.delete(f"/v1/projects/{project['id']}", headers=auth_header(token))
    response = client.get(f"/v1/projects/{project['id']}", headers=auth_header(token))

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

