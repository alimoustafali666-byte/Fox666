import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.tenancy.models import CompanyMember


def _signup(client: TestClient, email: str, company_name: str) -> tuple[str, dict]:
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


def _forge_token(claims: dict) -> str:
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def test_user_cannot_use_company_context_for_a_company_they_do_not_belong_to(
    client: TestClient,
) -> None:
    _, claims_a = _signup(client, "cross-a@acme.example.com", "Company A")
    _, claims_b = _signup(client, "cross-b@acme.example.com", "Company B")

    # A token that is validly signed but claims company B's id for user A
    # -- exactly what a compromised/misused token would look like. The
    # server must reject this on membership, not trust the claim.
    forged_claims = {**claims_a, "company_id": claims_b["company_id"]}
    forged_token = _forge_token(forged_claims)

    response = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {forged_token}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_role_is_read_from_the_database_not_trusted_from_the_token(
    client: TestClient, db_session: Session
) -> None:
    token, claims = _signup(client, "stale-role@acme.example.com", "Company Stale Role")
    assert claims["role"] == "owner"

    # Simulate the role having changed since the token was issued (e.g. a
    # future role-management step would do this) -- the DB row is now the
    # source of truth, the token's claim is stale.
    db_session.execute(
        update(CompanyMember)
        .where(CompanyMember.user_id == uuid.UUID(claims["sub"]))
        .values(role="member")
    )
    db_session.flush()

    response = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    # DB says "member" now; the token still says "owner" in its claims,
    # but the response must reflect the database, not the token.
    assert response.json()["role"] == "member"

