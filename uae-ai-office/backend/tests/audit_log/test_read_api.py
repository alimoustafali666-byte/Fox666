import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import set_company_context
from app.modules.audit_log.service import record_audit_event
from app.modules.auth.models import User
from app.modules.tenancy.models import CompanyMember


def _signup(client: TestClient, email: str, company_name: str = "Audit Read Co") -> tuple[str, dict]:
    response = client.post(
        "/v1/auth/signup",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "full_name": "Test User",
            "company_name": company_name,
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    return token, claims


def _seed_member(db_session: Session, *, company_id: uuid.UUID, email: str, role: str) -> str:
    user = User(email=email, password_hash=hash_password("irrelevant-password-value"), full_name="Seeded")
    db_session.add(user)
    db_session.flush()
    set_company_context(db_session, company_id)
    db_session.add(CompanyMember(company_id=company_id, user_id=user.id, role=role))
    db_session.flush()
    return create_access_token(user_id=user.id, company_id=company_id, role=role)


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# 11. owner can read company audit logs
def test_owner_can_read_audit_logs(client: TestClient) -> None:
    token, _ = _signup(client, "read-owner@example.com")

    response = client.get("/v1/audit-logs", headers=_auth_header(token))

    assert response.status_code == 200
    assert any(item["action"] == "auth.signup" for item in response.json()["items"])


# Regression test: TestClient's fake client host ("testclient") is never
# a parseable IP (see tests/audit_log/test_client_ip.py), so every other
# test in this file's audit rows have ip_address=None -- none of them
# would ever exercise the INET-column round trip. GET /v1/audit-logs
# used to 500 (pydantic ValidationError: ip_address must be a string,
# got ipaddress.IPv4Address) on any row where it wasn't null.
def test_reading_a_row_with_a_real_ip_address_does_not_500(
    client: TestClient, db_session: Session
) -> None:
    token, claims = _signup(client, "read-real-ip@example.com")
    company_id = uuid.UUID(claims["company_id"])
    set_company_context(db_session, company_id)
    record_audit_event(
        db_session, company_id=company_id, action="project.create",
        resource_type="project", ip_address="203.0.113.5",
    )
    db_session.flush()
    db_session.expire_all()

    response = client.get("/v1/audit-logs", headers=_auth_header(token))

    assert response.status_code == 200, response.text
    entry = next(item for item in response.json()["items"] if item["action"] == "project.create")
    assert entry["ip_address"] == "203.0.113.5"


# 12. admin can read company audit logs
def test_admin_can_read_audit_logs(client: TestClient, db_session: Session) -> None:
    _, owner_claims = _signup(client, "read-admin-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    admin_token = _seed_member(db_session, company_id=company_id, email="read-admin@example.com", role="admin")

    response = client.get("/v1/audit-logs", headers=_auth_header(admin_token))

    assert response.status_code == 200


# 13. manager cannot read audit logs
def test_manager_cannot_read_audit_logs(client: TestClient, db_session: Session) -> None:
    _, owner_claims = _signup(client, "read-manager-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    manager_token = _seed_member(
        db_session, company_id=company_id, email="read-manager@example.com", role="manager"
    )

    response = client.get("/v1/audit-logs", headers=_auth_header(manager_token))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


# 14. member cannot read audit logs
def test_member_cannot_read_audit_logs(client: TestClient, db_session: Session) -> None:
    _, owner_claims = _signup(client, "read-member-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    member_token = _seed_member(
        db_session, company_id=company_id, email="read-member@example.com", role="member"
    )

    response = client.get("/v1/audit-logs", headers=_auth_header(member_token))

    assert response.status_code == 403


# 15. Company A cannot read Company B audit logs
def test_company_a_cannot_read_company_b_audit_logs(client: TestClient) -> None:
    token_a, _ = _signup(client, "read-iso-a@example.com", "Company A")
    _, claims_b = _signup(client, "read-iso-b@example.com", "Company B")

    response = client.get("/v1/audit-logs", headers=_auth_header(token_a))

    assert response.status_code == 200
    actions_seen = {item["action"] for item in response.json()["items"]}
    # company A's own signup event should be present...
    assert "auth.signup" in actions_seen
    # ...but nothing from company B should ever be reachable through A's
    # token regardless of what B did.
    b_user_id = claims_b["sub"]
    assert all(item["actor_user_id"] != b_user_id for item in response.json()["items"])


# 16. client cannot override company_id to access another tenant
def test_client_supplied_company_id_query_param_has_no_effect(client: TestClient) -> None:
    token_a, claims_a = _signup(client, "read-override-a@example.com", "Company A")
    _, claims_b = _signup(client, "read-override-b@example.com", "Company B")

    response = client.get(
        f"/v1/audit-logs?company_id={claims_b['company_id']}", headers=_auth_header(token_a)
    )

    assert response.status_code == 200
    b_user_id = claims_b["sub"]
    assert all(item["actor_user_id"] != b_user_id for item in response.json()["items"])
    # and everything returned is still attributable to A's own signup
    assert any(item["actor_user_id"] == claims_a["sub"] for item in response.json()["items"])


# 17. pagination is bounded
def test_pagination_is_bounded_and_covers_all_rows_without_duplicates(
    client: TestClient, db_session: Session
) -> None:
    token, claims = _signup(client, "read-paginate@example.com")
    company_id = uuid.UUID(claims["company_id"])
    set_company_context(db_session, company_id)
    for i in range(25):
        record_audit_event(
            db_session, company_id=company_id, action="system.probe", resource_type="system",
            metadata={"i": i},
        )
    db_session.flush()

    seen_ids: set[str] = set()
    cursor = None
    pages = 0
    while True:
        url = "/v1/audit-logs?limit=10"
        if cursor:
            url += f"&cursor={cursor}"
        response = client.get(url, headers=_auth_header(token))
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) <= 10
        for item in body["items"]:
            assert item["id"] not in seen_ids, "pagination must not return duplicate rows"
            seen_ids.add(item["id"])
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break
        assert pages < 20, "pagination did not terminate"

    # 25 probes + 1 signup event = 26
    assert len(seen_ids) == 26


def test_pagination_limit_is_capped_at_the_maximum(client: TestClient) -> None:
    token, _ = _signup(client, "read-paginate-cap@example.com")

    response = client.get("/v1/audit-logs?limit=99999", headers=_auth_header(token))

    assert response.status_code == 422  # FastAPI's Query(le=...) validation


# 18. supported filters work
def test_action_filter_works(client: TestClient, db_session: Session) -> None:
    token, claims = _signup(client, "read-filter-action@example.com")
    company_id = uuid.UUID(claims["company_id"])
    set_company_context(db_session, company_id)
    record_audit_event(db_session, company_id=company_id, action="project.create", resource_type="project")
    db_session.flush()

    response = client.get("/v1/audit-logs?action=project.create", headers=_auth_header(token))

    assert response.status_code == 200
    assert all(item["action"] == "project.create" for item in response.json()["items"])
    assert len(response.json()["items"]) == 1


def test_resource_type_filter_works(client: TestClient, db_session: Session) -> None:
    token, claims = _signup(client, "read-filter-resource@example.com")
    company_id = uuid.UUID(claims["company_id"])
    set_company_context(db_session, company_id)
    record_audit_event(db_session, company_id=company_id, action="document.upload", resource_type="document")
    db_session.flush()

    response = client.get("/v1/audit-logs?resource_type=document", headers=_auth_header(token))

    assert response.status_code == 200
    assert all(item["resource_type"] == "document" for item in response.json()["items"])


def test_actor_user_id_filter_works(client: TestClient, db_session: Session) -> None:
    token, claims = _signup(client, "read-filter-actor@example.com")
    user_id = claims["sub"]

    response = client.get(f"/v1/audit-logs?actor_user_id={user_id}", headers=_auth_header(token))

    assert response.status_code == 200
    assert all(item["actor_user_id"] == user_id for item in response.json()["items"])
    assert len(response.json()["items"]) >= 1


def test_date_range_filters_work(client: TestClient) -> None:
    token, _ = _signup(client, "read-filter-date@example.com")

    far_future = "2099-01-01T00:00:00Z"
    response = client.get(f"/v1/audit-logs?date_from={far_future}", headers=_auth_header(token))

    assert response.status_code == 200
    assert response.json()["items"] == []


# 19. malformed filter input is handled safely
def test_malformed_actor_user_id_returns_422_not_500(client: TestClient) -> None:
    token, _ = _signup(client, "read-malformed-actor@example.com")

    response = client.get("/v1/audit-logs?actor_user_id=not-a-uuid", headers=_auth_header(token))

    assert response.status_code == 422


def test_malformed_date_returns_422_not_500(client: TestClient) -> None:
    token, _ = _signup(client, "read-malformed-date@example.com")

    response = client.get("/v1/audit-logs?date_from=not-a-date", headers=_auth_header(token))

    assert response.status_code == 422


def test_malformed_cursor_returns_400_not_500(client: TestClient) -> None:
    token, _ = _signup(client, "read-malformed-cursor@example.com")

    response = client.get("/v1/audit-logs?cursor=not-a-valid-cursor!!!", headers=_auth_header(token))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


def test_unknown_action_filter_returns_empty_not_error(client: TestClient) -> None:
    token, _ = _signup(client, "read-unknown-action@example.com")

    response = client.get(
        "/v1/audit-logs?action=totally.unknown_action", headers=_auth_header(token)
    )

    assert response.status_code == 200
    assert response.json()["items"] == []

