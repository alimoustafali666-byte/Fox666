import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import set_company_context
from app.modules.auth.models import User
from app.modules.tenancy.models import CompanyMember


def signup(client: TestClient, email: str, company_name: str = "Projects Test Co") -> tuple[str, dict]:
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


def seed_member(db_session: Session, *, company_id: uuid.UUID, email: str, role: str) -> str:
    """Adds a member with an arbitrary role directly at the DB layer --
    there is no invitation API yet, so this stands in for "a membership
    that legitimately exists with this role" for RBAC testing.
    """
    user = User(
        email=email, password_hash=hash_password("irrelevant-password-value"), full_name="Seeded"
    )
    db_session.add(user)
    db_session.flush()

    set_company_context(db_session, company_id)
    db_session.add(CompanyMember(company_id=company_id, user_id=user.id, role=role))
    db_session.flush()

    return create_access_token(user_id=user.id, company_id=company_id, role=role)


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

