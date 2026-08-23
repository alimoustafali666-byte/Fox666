import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import set_company_context
from tests.projects.helpers import auth_header, seed_member, signup


def _create(client: TestClient, token: str, **kwargs) -> dict:
    payload = {"name": "Project"} | kwargs
    response = client.post("/v1/projects", json=payload, headers=auth_header(token))
    assert response.status_code == 201
    return response.json()


# 13. owner can list only own-company projects
def test_owner_lists_only_own_company_projects(client: TestClient) -> None:
    token_a, _ = signup(client, "list-owner-a@example.com", "Company A")
    token_b, _ = signup(client, "list-owner-b@example.com", "Company B")
    _create(client, token_a, name="A's Project")
    _create(client, token_b, name="B's Project")

    response = client.get("/v1/projects", headers=auth_header(token_a))

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["items"]}
    assert names == {"A's Project"}


# 14. admin can list own-company projects
def test_admin_can_list_projects(client: TestClient, db_session: Session) -> None:
    _, owner_claims = signup(client, "list-admin-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    admin_token = seed_member(db_session, company_id=company_id, email="list-admin@example.com", role="admin")

    response = client.get("/v1/projects", headers=auth_header(admin_token))

    assert response.status_code == 200


# 15. manager can read projects
def test_manager_can_read_projects(client: TestClient, db_session: Session) -> None:
    _, owner_claims = signup(client, "list-manager-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    manager_token = seed_member(
        db_session, company_id=company_id, email="list-manager@example.com", role="manager"
    )

    response = client.get("/v1/projects", headers=auth_header(manager_token))

    assert response.status_code == 200


# 16. member can read projects
def test_member_can_read_projects(client: TestClient, db_session: Session) -> None:
    _, owner_claims = signup(client, "list-member-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    member_token = seed_member(
        db_session, company_id=company_id, email="list-member@example.com", role="member"
    )

    response = client.get("/v1/projects", headers=auth_header(member_token))

    assert response.status_code == 200


# 17. status filter works
def test_status_filter_works(client: TestClient) -> None:
    token, _ = signup(client, "list-filter-status@example.com")
    _create(client, token, name="Planning One")
    _create(client, token, name="Active One", status="active")

    response = client.get("/v1/projects?status=active", headers=auth_header(token))

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Active One"


# 18. project_code filter works
def test_project_code_filter_works(client: TestClient) -> None:
    token, _ = signup(client, "list-filter-code@example.com")
    _create(client, token, name="Coded", project_code="ABC-1")
    _create(client, token, name="Uncoded")

    response = client.get("/v1/projects?project_code=ABC-1", headers=auth_header(token))

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["project_code"] == "ABC-1"


# 19. basic name search works
def test_name_search_works(client: TestClient) -> None:
    token, _ = signup(client, "list-search-name@example.com")
    _create(client, token, name="Marina Tower Renovation")
    _create(client, token, name="Downtown Office Fitout")

    response = client.get("/v1/projects?name=marina", headers=auth_header(token))

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert "Marina" in items[0]["name"]


# 20. pagination is bounded
def test_pagination_is_bounded(client: TestClient) -> None:
    token, _ = signup(client, "list-paginate@example.com")
    for i in range(15):
        _create(client, token, name=f"Project {i}")

    response = client.get("/v1/projects?limit=10", headers=auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 10
    assert body["next_cursor"] is not None

    second_page = client.get(
        f"/v1/projects?limit=10&cursor={body['next_cursor']}", headers=auth_header(token)
    )
    assert len(second_page.json()["items"]) == 5
    assert second_page.json()["next_cursor"] is None


def test_pagination_limit_is_capped(client: TestClient) -> None:
    token, _ = signup(client, "list-paginate-cap@example.com")

    response = client.get("/v1/projects?limit=99999", headers=auth_header(token))

    assert response.status_code == 422


def test_default_ordering_is_newest_first(client: TestClient, db_session: Session) -> None:
    """created_at defaults to now(), which Postgres freezes for the whole
    transaction -- and this test suite deliberately runs each test inside
    one transaction (see conftest.py), so two real inserts a moment apart
    would get an *identical* created_at here, making order-by-timestamp
    genuinely random rather than flaky-by-timing. Setting created_at
    explicitly makes the ordering assertion deterministic without
    changing how the app itself behaves (a real deployment commits each
    request as its own transaction, so this collision doesn't occur
    outside this kind of test harness).
    """
    token, claims = signup(client, "list-order@example.com")
    first = _create(client, token, name="First Created")
    second = _create(client, token, name="Second Created")

    set_company_context(db_session, uuid.UUID(claims["company_id"]))
    db_session.execute(
        text("UPDATE projects SET created_at = :t WHERE id = :id"),
        {"t": datetime.now(UTC) - timedelta(seconds=10), "id": uuid.UUID(first["id"])},
    )
    db_session.execute(
        text("UPDATE projects SET created_at = :t WHERE id = :id"),
        {"t": datetime.now(UTC), "id": uuid.UUID(second["id"])},
    )
    db_session.flush()

    response = client.get("/v1/projects", headers=auth_header(token))

    names = [item["name"] for item in response.json()["items"]]
    assert names == ["Second Created", "First Created"]


def test_unknown_status_filter_is_rejected_cleanly_not_a_db_error(client: TestClient) -> None:
    """Unlike audit-log's plain-TEXT filters (where an unknown value just
    matches nothing), projects.status is a native Postgres enum -- an
    invalid value isn't a valid query at all, so this must fail as a
    clean 4xx before it ever reaches SQL, never an unhandled 500 that
    would otherwise leak a raw database error.
    """
    token, _ = signup(client, "list-unknown-status@example.com")
    _create(client, token, name="Some Project")

    response = client.get("/v1/projects?status=not_a_real_status", headers=auth_header(token))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


def test_project_code_filter_with_unmatched_value_returns_empty_not_error(client: TestClient) -> None:
    """project_code, unlike status, is plain TEXT -- an unmatched value
    is a legitimate "no rows" rather than an invalid query.
    """
    token, _ = signup(client, "list-unmatched-code@example.com")
    _create(client, token, name="Some Project", project_code="REAL-CODE")

    response = client.get("/v1/projects?project_code=NO-SUCH-CODE", headers=auth_header(token))

    assert response.status_code == 200
    assert response.json()["items"] == []

