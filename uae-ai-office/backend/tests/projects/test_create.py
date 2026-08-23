import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.projects.helpers import auth_header, seed_member, signup


# 1. owner can create project
def test_owner_can_create_project(client: TestClient) -> None:
    token, _ = signup(client, "create-owner@example.com")

    response = client.post("/v1/projects", json={"name": "Owner Project"}, headers=auth_header(token))

    assert response.status_code == 201
    assert response.json()["name"] == "Owner Project"


# 2. admin can create project
def test_admin_can_create_project(client: TestClient, db_session: Session) -> None:
    _, owner_claims = signup(client, "create-admin-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    admin_token = seed_member(db_session, company_id=company_id, email="create-admin@example.com", role="admin")

    response = client.post(
        "/v1/projects", json={"name": "Admin Project"}, headers=auth_header(admin_token)
    )

    assert response.status_code == 201


# 3. manager can create project
def test_manager_can_create_project(client: TestClient, db_session: Session) -> None:
    _, owner_claims = signup(client, "create-manager-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    manager_token = seed_member(
        db_session, company_id=company_id, email="create-manager@example.com", role="manager"
    )

    response = client.post(
        "/v1/projects", json={"name": "Manager Project"}, headers=auth_header(manager_token)
    )

    assert response.status_code == 201


# 4. member cannot create project
def test_member_cannot_create_project(client: TestClient, db_session: Session) -> None:
    _, owner_claims = signup(client, "create-member-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    member_token = seed_member(
        db_session, company_id=company_id, email="create-member@example.com", role="member"
    )

    response = client.post(
        "/v1/projects", json={"name": "Member Project"}, headers=auth_header(member_token)
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


# 5. project company_id is server-resolved
def test_project_company_id_is_server_resolved(client: TestClient) -> None:
    token, claims = signup(client, "create-resolved@example.com")

    response = client.post("/v1/projects", json={"name": "Resolved"}, headers=auth_header(token))

    assert response.json()["company_id"] == claims["company_id"]


# 6. client cannot inject company_id
def test_client_cannot_inject_company_id(client: TestClient) -> None:
    token, claims = signup(client, "create-inject@example.com")
    forged_company_id = str(uuid.uuid4())

    response = client.post(
        "/v1/projects",
        json={"name": "Injected", "company_id": forged_company_id},
        headers=auth_header(token),
    )

    assert response.status_code == 201  # extra field silently ignored, not an error
    assert response.json()["company_id"] == claims["company_id"]
    assert response.json()["company_id"] != forged_company_id


# 7. default status is planning
def test_default_status_is_planning(client: TestClient) -> None:
    token, _ = signup(client, "create-default-status@example.com")

    response = client.post("/v1/projects", json={"name": "Default Status"}, headers=auth_header(token))

    assert response.json()["status"] == "planning"


# 8. valid explicit status works
def test_valid_explicit_status_works(client: TestClient) -> None:
    token, _ = signup(client, "create-explicit-status@example.com")

    response = client.post(
        "/v1/projects", json={"name": "Active One", "status": "active"}, headers=auth_header(token)
    )

    assert response.status_code == 201
    assert response.json()["status"] == "active"


# 9. invalid status is rejected
def test_invalid_status_is_rejected(client: TestClient) -> None:
    token, _ = signup(client, "create-invalid-status@example.com")

    response = client.post(
        "/v1/projects",
        json={"name": "Bad Status", "status": "not_a_real_status"},
        headers=auth_header(token),
    )

    assert response.status_code == 422


# 10. project_code may be null
def test_project_code_may_be_null(client: TestClient) -> None:
    token, _ = signup(client, "create-null-code@example.com")

    response = client.post("/v1/projects", json={"name": "No Code"}, headers=auth_header(token))

    assert response.status_code == 201
    assert response.json()["project_code"] is None


# 11. duplicate non-null project_code in same company is rejected safely
def test_duplicate_project_code_in_same_company_is_rejected_safely(client: TestClient) -> None:
    token, _ = signup(client, "create-dup-code@example.com")
    client.post(
        "/v1/projects", json={"name": "First", "project_code": "PRJ-1"}, headers=auth_header(token)
    )

    response = client.post(
        "/v1/projects", json={"name": "Second", "project_code": "PRJ-1"}, headers=auth_header(token)
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "project_code_already_exists"
    # must not leak SQL/constraint details or the other project's identity
    body_text = str(body)
    for forbidden in ("uq_projects_company_code", "IntegrityError", "First", "duplicate key"):
        assert forbidden not in body_text


# 12. same project_code in different companies is allowed
def test_same_project_code_allowed_across_different_companies(client: TestClient) -> None:
    token_a, _ = signup(client, "create-samecode-a@example.com", "Company A")
    token_b, _ = signup(client, "create-samecode-b@example.com", "Company B")

    response_a = client.post(
        "/v1/projects", json={"name": "A's Project", "project_code": "SHARED"}, headers=auth_header(token_a)
    )
    response_b = client.post(
        "/v1/projects", json={"name": "B's Project", "project_code": "SHARED"}, headers=auth_header(token_b)
    )

    assert response_a.status_code == 201
    assert response_b.status_code == 201


def test_blank_name_is_rejected(client: TestClient) -> None:
    token, _ = signup(client, "create-blank-name@example.com")

    response = client.post("/v1/projects", json={"name": "   "}, headers=auth_header(token))

    assert response.status_code == 422


def test_name_is_trimmed(client: TestClient) -> None:
    token, _ = signup(client, "create-trim-name@example.com")

    response = client.post(
        "/v1/projects", json={"name": "  Trimmed Name  "}, headers=auth_header(token)
    )

    assert response.json()["name"] == "Trimmed Name"


def test_overly_long_name_is_rejected(client: TestClient) -> None:
    token, _ = signup(client, "create-long-name@example.com")

    response = client.post(
        "/v1/projects", json={"name": "x" * 500}, headers=auth_header(token)
    )

    assert response.status_code == 422

