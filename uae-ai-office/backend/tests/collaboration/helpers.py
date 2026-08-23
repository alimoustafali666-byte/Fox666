import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import set_company_context
from app.modules.auth.models import User
from app.modules.tenancy.models import CompanyMember


def signup(client: TestClient, email: str, company_name: str = "Collab Test Co", full_name: str = "Test User") -> tuple[str, dict]:
    response = client.post(
        "/v1/auth/signup",
        json={"email": email, "password": "correct horse battery staple", "full_name": full_name, "company_name": company_name},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    return token, claims


def seed_member(db_session: Session, *, company_id: uuid.UUID, email: str, role: str, full_name: str = "Seeded") -> tuple[str, uuid.UUID]:
    user = User(email=email, password_hash=hash_password("irrelevant-password-value"), full_name=full_name)
    db_session.add(user)
    db_session.flush()
    set_company_context(db_session, company_id)
    db_session.add(CompanyMember(company_id=company_id, user_id=user.id, role=role))
    db_session.flush()
    return create_access_token(user_id=user.id, company_id=company_id, role=role), user.id


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def create_direct(client: TestClient, token: str, other_user_id: uuid.UUID) -> dict:
    response = client.post(
        "/v1/collaboration/conversations/direct", json={"other_user_id": str(other_user_id)}, headers=auth_header(token)
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_group(client: TestClient, token: str, *, name: str = "Test Group", member_user_ids: list[uuid.UUID] | None = None) -> dict:
    response = client.post(
        "/v1/collaboration/conversations/group",
        json={"name": name, "member_user_ids": [str(u) for u in (member_user_ids or [])]},
        headers=auth_header(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def send_message(client: TestClient, token: str, conversation_id, content: str = "Hello", **kwargs) -> dict:
    payload = {"content": content, **kwargs}
    response = client.post(f"/v1/collaboration/conversations/{conversation_id}/messages", json=payload, headers=auth_header(token))
    assert response.status_code == 201, response.text
    return response.json()

