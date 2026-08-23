import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import delete, text, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import set_company_context
from app.modules.auth.models import User
from app.modules.tenancy.models import CompanyMember


def _signup(client: TestClient, email: str, company_name: str = "Acme Contracting") -> tuple[str, dict]:
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


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _forge_token(claims: dict) -> str:
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


# 1. unauthenticated protected request is rejected
def test_unauthenticated_request_is_rejected(client: TestClient) -> None:
    response = client.get("/v1/companies/current")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


# 2. valid user can access their active company
def test_valid_user_can_access_their_active_company(client: TestClient) -> None:
    token, claims = _signup(client, "context-valid@example.com")

    response = client.get("/v1/companies/current", headers=_auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["company"]["id"] == claims["company_id"]
    assert body["role"] == "owner"


# 3. inactive user is rejected
def test_inactive_user_is_rejected(client: TestClient, db_session: Session) -> None:
    token, claims = _signup(client, "context-inactive@example.com")
    db_session.execute(
        update(User).where(User.id == uuid.UUID(claims["sub"])).values(is_active=False)
    )
    db_session.flush()

    response = client.get("/v1/companies/current", headers=_auth_header(token))

    assert response.status_code == 401


# 4. removed membership invalidates access even with previously valid JWT
# 21. deleting/removing membership immediately blocks future protected requests
def test_removed_membership_invalidates_a_previously_valid_jwt(
    client: TestClient, db_session: Session
) -> None:
    token, claims = _signup(client, "context-removed@example.com")

    # confirm access works before removal
    assert client.get("/v1/companies/current", headers=_auth_header(token)).status_code == 200

    db_session.execute(
        delete(CompanyMember).where(CompanyMember.user_id == uuid.UUID(claims["sub"]))
    )
    db_session.flush()

    response = client.get("/v1/companies/current", headers=_auth_header(token))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


# regression: a malformed sub/company_id claim must fail cleanly (401),
# not surface a raw ValueError as an unhandled 500.
def test_malformed_claims_are_rejected_cleanly_not_as_a_server_error(client: TestClient) -> None:
    _, claims = _signup(client, "context-malformed@example.com")

    bad_sub = _forge_token({**claims, "sub": "not-a-uuid"})
    response = client.get("/v1/companies/current", headers=_auth_header(bad_sub))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"

    bad_company = _forge_token({**claims, "company_id": "also-not-a-uuid"})
    response = client.get("/v1/companies/current", headers=_auth_header(bad_company))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


# 5. JWT company_id for unrelated company is rejected
def test_jwt_company_id_for_unrelated_company_is_rejected(client: TestClient) -> None:
    _, claims_a = _signup(client, "context-cross-a@example.com", "Company A")
    _, claims_b = _signup(client, "context-cross-b@example.com", "Company B")

    forged = _forge_token({**claims_a, "company_id": claims_b["company_id"]})

    response = client.get("/v1/companies/current", headers=_auth_header(forged))

    assert response.status_code == 401


# 6. JWT role manipulation cannot elevate privileges
def test_jwt_role_manipulation_cannot_elevate_privileges(client: TestClient, db_session: Session) -> None:
    _, claims = _signup(client, "context-elevate@example.com")
    # DB says owner today, but force it down to "member" to simulate a
    # role change since the token was issued, then forge a token that
    # still (falsely) claims "owner".
    db_session.execute(
        update(CompanyMember)
        .where(CompanyMember.user_id == uuid.UUID(claims["sub"]))
        .values(role="member")
    )
    db_session.flush()
    forged_owner_claim = _forge_token({**claims, "role": "owner"})

    response = client.get(
        "/v1/companies/current/members", headers=_auth_header(forged_owner_claim)
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


# 7. authoritative role comes from database
def test_role_is_read_from_database_not_token(client: TestClient, db_session: Session) -> None:
    token, claims = _signup(client, "context-dbrole@example.com")
    db_session.execute(
        update(CompanyMember)
        .where(CompanyMember.user_id == uuid.UUID(claims["sub"]))
        .values(role="manager")
    )
    db_session.flush()

    response = client.get("/v1/companies/current", headers=_auth_header(token))

    assert response.status_code == 200
    assert response.json()["role"] == "manager"  # not "owner", which the token still claims


# 15. missing tenant context returns zero tenant rows / fails closed
def test_missing_tenant_context_fails_closed_at_the_database_layer(
    client: TestClient, db_session: Session
) -> None:
    _signup(client, "context-failclosed@example.com")

    set_company_context(db_session, None)
    rows = db_session.execute(text("SELECT id FROM company_members")).all()

    assert rows == []


# 16 & 17. app.current_user_id / app.current_company_id are set correctly
def test_tenant_context_sets_both_session_variables_correctly(
    client: TestClient, db_session: Session
) -> None:
    token, claims = _signup(client, "context-vars@example.com")

    client.get("/v1/companies/current", headers=_auth_header(token))

    # db_session is the exact same Session the request handler used
    # (dependency-overridden), so whatever it SET LOCAL is still visible
    # here, within the same still-open transaction.
    seen_user = db_session.execute(
        text("SELECT current_setting('app.current_user_id', true)")
    ).scalar_one()
    seen_company = db_session.execute(
        text("SELECT current_setting('app.current_company_id', true)")
    ).scalar_one()

    assert seen_user == claims["sub"]
    assert seen_company == claims["company_id"]


# 20. changing membership role in DB takes effect without needing to trust old JWT role
def test_stale_but_validly_signed_token_reflects_live_db_role_change(
    client: TestClient, db_session: Session
) -> None:
    token, claims = _signup(client, "context-stale@example.com")
    assert client.get(
        "/v1/companies/current/members", headers=_auth_header(token)
    ).status_code == 200  # owner can list members

    db_session.execute(
        update(CompanyMember)
        .where(CompanyMember.user_id == uuid.UUID(claims["sub"]))
        .values(role="member")
    )
    db_session.flush()

    # same, still-unexpired, never-forged token -- but the endpoint's
    # authorization outcome must change because the DB role changed.
    response = client.get("/v1/companies/current/members", headers=_auth_header(token))

    assert response.status_code == 403

