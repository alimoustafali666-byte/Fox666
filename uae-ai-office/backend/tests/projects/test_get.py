import uuid

from fastapi.testclient import TestClient

from tests.projects.helpers import auth_header, signup


def _create(client: TestClient, token: str, **kwargs) -> dict:
    payload = {"name": "Project"} | kwargs
    response = client.post("/v1/projects", json=payload, headers=auth_header(token))
    assert response.status_code == 201
    return response.json()


def test_owner_can_get_own_project(client: TestClient) -> None:
    token, _ = signup(client, "get-own@example.com")
    project = _create(client, token, name="Gettable")

    response = client.get(f"/v1/projects/{project['id']}", headers=auth_header(token))

    assert response.status_code == 200
    assert response.json()["id"] == project["id"]


# 21. cross-company project ID cannot be read
def test_cross_company_project_id_cannot_be_read(client: TestClient) -> None:
    token_a, _ = signup(client, "get-iso-a@example.com", "Company A")
    token_b, _ = signup(client, "get-iso-b@example.com", "Company B")
    project_b = _create(client, token_b, name="B's Secret Project")

    response = client.get(f"/v1/projects/{project_b['id']}", headers=auth_header(token_a))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "project_not_found"


def test_nonexistent_project_id_returns_identical_not_found(client: TestClient) -> None:
    """IDOR safety: "belongs to another tenant" and "never existed" must
    be indistinguishable from the response.
    """
    token, _ = signup(client, "get-notfound@example.com")

    real_missing = client.get(f"/v1/projects/{uuid.uuid4()}", headers=auth_header(token))

    assert real_missing.status_code == 404
    assert real_missing.json()["error"]["code"] == "project_not_found"

