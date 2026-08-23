import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import set_company_context
from app.modules.auth.models import User
from app.modules.tenancy.models import CompanyMember


def _signup(client: TestClient, email: str) -> tuple[str, dict]:
    response = client.post(
        "/v1/auth/signup",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "full_name": "Owner User",
            "company_name": "RBAC Test Co",
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    return token, claims


def _seed_member(db_session: Session, *, company_id: uuid.UUID, email: str, role: str) -> str:
    """Adds a member with an arbitrary role directly at the DB layer --
    there is no invitation API yet (out of scope for this step), so this
    stands in for "a membership that legitimately exists with this role",
    which is all the RBAC mechanism itself needs to be tested against.
    """
    user = User(email=email, password_hash=hash_password("irrelevant-password-value"), full_name="Seeded User")
    db_session.add(user)
    db_session.flush()

    set_company_context(db_session, company_id)
    db_session.add(CompanyMember(company_id=company_id, user_id=user.id, role=role))
    db_session.flush()

    return create_access_token(user_id=user.id, company_id=company_id, role=role)


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# 8. member cannot access owner/admin-only endpoint
def test_member_cannot_access_owner_admin_only_endpoint(
    client: TestClient, db_session: Session
) -> None:
    _, owner_claims = _signup(client, "rbac-member-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    member_token = _seed_member(db_session, company_id=company_id, email="rbac-member@example.com", role="member")

    response = client.get("/v1/companies/current/members", headers=_auth_header(member_token))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


# 9. manager cannot access owner/admin-only endpoint unless explicitly allowed
def test_manager_cannot_access_owner_admin_only_endpoint(
    client: TestClient, db_session: Session
) -> None:
    _, owner_claims = _signup(client, "rbac-manager-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    manager_token = _seed_member(
        db_session, company_id=company_id, email="rbac-manager@example.com", role="manager"
    )

    response = client.get("/v1/companies/current/members", headers=_auth_header(manager_token))

    assert response.status_code == 403


# 10. admin can access member-list endpoint
def test_admin_can_access_member_list_endpoint(client: TestClient, db_session: Session) -> None:
    _, owner_claims = _signup(client, "rbac-admin-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    admin_token = _seed_member(db_session, company_id=company_id, email="rbac-admin@example.com", role="admin")

    response = client.get("/v1/companies/current/members", headers=_auth_header(admin_token))

    assert response.status_code == 200


# 11. owner can access member-list endpoint
def test_owner_can_access_member_list_endpoint(client: TestClient) -> None:
    owner_token, _ = _signup(client, "rbac-owner-self@example.com")

    response = client.get("/v1/companies/current/members", headers=_auth_header(owner_token))

    assert response.status_code == 200


# 12. company member listing never exposes password/token/security fields
def test_member_listing_never_exposes_sensitive_fields(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = _signup(client, "rbac-safe-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    _seed_member(db_session, company_id=company_id, email="rbac-safe-member@example.com", role="member")

    response = client.get("/v1/companies/current/members", headers=_auth_header(owner_token))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    body_text = str(body)
    for forbidden in ("password", "password_hash", "token_hash", "refresh_token", "token"):
        assert forbidden not in body_text
    for entry in body:
        assert set(entry.keys()) == {"user_id", "email", "full_name", "role", "created_at"}

