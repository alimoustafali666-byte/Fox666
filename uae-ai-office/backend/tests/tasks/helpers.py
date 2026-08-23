import uuid
from datetime import UTC, datetime

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import set_company_context
from app.modules.auth.models import User
from app.modules.briefs.models import BriefItem, DailyBrief
from app.modules.tenancy.models import CompanyMember


def signup(client: TestClient, email: str, company_name: str = "Tasks Test Co", full_name: str = "Test Owner") -> tuple[str, dict]:
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


def create_project(client: TestClient, token: str, name: str = "Test Project") -> dict:
    response = client.post("/v1/projects", json={"name": name}, headers=auth_header(token))
    assert response.status_code == 201, response.text
    return response.json()


def create_task(client: TestClient, token: str, *, title: str = "A task", **kwargs) -> dict:
    payload = {"title": title, **kwargs}
    response = client.post("/v1/tasks", json=payload, headers=auth_header(token))
    assert response.status_code == 201, response.text
    return response.json()


def seed_brief_item(
    db_session: Session, *, company_id: uuid.UUID, generated_by: uuid.UUID, category: str = "pending_action", text: str = "Send the revised quotation"
) -> BriefItem:
    """Directly inserts a DailyBrief + BriefItem via the ORM -- brief
    GENERATION (the AI orchestration pipeline) is Step 12's own concern
    and already has its own test suite; this module only needs a real,
    persisted brief item to validate against when testing Tasks'
    source-reference re-validation.
    """
    set_company_context(db_session, company_id)
    brief = DailyBrief(
        id=uuid.uuid4(), company_id=company_id, generated_by=generated_by,
        brief_date=datetime.now(UTC).date(), summary="Test brief", generated_at=datetime.now(UTC),
    )
    db_session.add(brief)
    db_session.flush()
    item = BriefItem(id=uuid.uuid4(), company_id=company_id, brief_id=brief.id, category=category, text=text, priority=2)
    db_session.add(item)
    db_session.flush()
    return item

