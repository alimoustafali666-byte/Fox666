import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.projects.helpers import auth_header, seed_member, signup


def _create(client: TestClient, token: str, **kwargs) -> dict:
    payload = {"name": "Project"} | kwargs
    response = client.post("/v1/projects", json=payload, headers=auth_header(token))
    assert response.status_code == 201
    return response.json()


# 24. owner can update project
def test_owner_can_update_project(client: TestClient) -> None:
    token, _ = signup(client, "update-owner@example.com")
    project = _create(client, token, name="Original")

    response = client.patch(
        f"/v1/projects/{project['id']}", json={"name": "Updated"}, headers=auth_header(token)
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated"


# 25. admin can update project
def test_admin_can_update_project(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "update-admin-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    project = _create(client, owner_token, name="Original")
    admin_token = seed_member(db_session, company_id=company_id, email="update-admin@example.com", role="admin")

    response = client.patch(
        f"/v1/projects/{project['id']}", json={"name": "Updated by admin"}, headers=auth_header(admin_token)
    )

    assert response.status_code == 200


# 26. manager can update project
def test_manager_can_update_project(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "update-manager-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    project = _create(client, owner_token, name="Original")
    manager_token = seed_member(
        db_session, company_id=company_id, email="update-manager@example.com", role="manager"
    )

    response = client.patch(
        f"/v1/projects/{project['id']}",
        json={"name": "Updated by manager"},
        headers=auth_header(manager_token),
    )

    assert response.status_code == 200


# 27. member cannot update project
def test_member_cannot_update_project(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "update-member-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    project = _create(client, owner_token, name="Original")
    member_token = seed_member(
        db_session, company_id=company_id, email="update-member@example.com", role="member"
    )

    response = client.patch(
        f"/v1/projects/{project['id']}",
        json={"name": "Should not work"},
        headers=auth_header(member_token),
    )

    assert response.status_code == 403


# 22. cross-company project ID cannot be updated
def test_cross_company_project_id_cannot_be_updated(client: TestClient) -> None:
    token_a, _ = signup(client, "update-iso-a@example.com", "Company A")
    token_b, _ = signup(client, "update-iso-b@example.com", "Company B")
    project_b = _create(client, token_b, name="B's Project")

    response = client.patch(
        f"/v1/projects/{project_b['id']}", json={"name": "Hijacked"}, headers=auth_header(token_a)
    )

    assert response.status_code == 404


# 28. protected fields cannot be changed
def test_protected_fields_cannot_be_changed(client: TestClient) -> None:
    token, claims = signup(client, "update-protected@example.com")
    project = _create(client, token, name="Original")
    original_id = project["id"]
    original_created_at = project["created_at"]

    forged_id = str(uuid.uuid4())
    forged_company_id = str(uuid.uuid4())
    response = client.patch(
        f"/v1/projects/{project['id']}",
        json={
            "id": forged_id,
            "company_id": forged_company_id,
            "created_at": "2000-01-01T00:00:00Z",
            "name": "Still allowed to change",
        },
        headers=auth_header(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == original_id
    assert body["company_id"] == claims["company_id"]
    assert body["created_at"] == original_created_at
    assert body["name"] == "Still allowed to change"


def test_partial_update_only_touches_specified_fields(client: TestClient) -> None:
    token, _ = signup(client, "update-partial@example.com")
    project = _create(client, token, name="Original", description="Original description", project_code="CODE-1")

    response = client.patch(
        f"/v1/projects/{project['id']}", json={"status": "active"}, headers=auth_header(token)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert body["name"] == "Original"
    assert body["description"] == "Original description"
    assert body["project_code"] == "CODE-1"


def test_explicit_null_clears_project_code(client: TestClient) -> None:
    token, _ = signup(client, "update-clear-code@example.com")
    project = _create(client, token, name="Coded", project_code="TO-CLEAR")

    response = client.patch(
        f"/v1/projects/{project['id']}", json={"project_code": None}, headers=auth_header(token)
    )

    assert response.status_code == 200
    assert response.json()["project_code"] is None


def test_update_to_duplicate_project_code_is_rejected(client: TestClient) -> None:
    token, _ = signup(client, "update-dup-code@example.com")
    _create(client, token, name="First", project_code="TAKEN")
    second = _create(client, token, name="Second", project_code="AVAILABLE")

    response = client.patch(
        f"/v1/projects/{second['id']}", json={"project_code": "TAKEN"}, headers=auth_header(token)
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "project_code_already_exists"


def test_update_with_invalid_status_is_rejected(client: TestClient) -> None:
    token, _ = signup(client, "update-invalid-status@example.com")
    project = _create(client, token, name="Original")

    response = client.patch(
        f"/v1/projects/{project['id']}",
        json={"status": "not_a_real_status"},
        headers=auth_header(token),
    )

    assert response.status_code == 422


def test_update_with_empty_body_is_a_no_op(client: TestClient) -> None:
    token, _ = signup(client, "update-empty@example.com")
    project = _create(client, token, name="Unchanged")

    response = client.patch(f"/v1/projects/{project['id']}", json={}, headers=auth_header(token))

    assert response.status_code == 200
    assert response.json()["name"] == "Unchanged"

