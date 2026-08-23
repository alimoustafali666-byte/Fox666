import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import set_company_context
from app.modules.auth.models import User
from app.modules.tenancy.models import CompanyMember

PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< >>\nendobj\n%%EOF"


def signup(client: TestClient, email: str, company_name: str = "Support Test Co") -> tuple[str, dict]:
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


def create_ticket(
    client: TestClient,
    token: str,
    *,
    category: str = "documents",
    subject: str = "Test subject",
    description: str = "Test description of the issue.",
    priority: str = "normal",
    diagnostics: dict | None = None,
) -> dict:
    payload = {
        "category": category,
        "subject": subject,
        "description": description,
        "priority": priority,
    }
    if diagnostics is not None:
        payload["diagnostics"] = diagnostics
    response = client.post("/v1/support/tickets", json=payload, headers=auth_header(token))
    assert response.status_code == 201, response.text
    return response.json()


def upload_document(
    client: TestClient, token: str, *, filename: str = "contract.pdf", document_type: str = "contract"
) -> dict:
    response = client.post(
        "/v1/documents",
        headers=auth_header(token),
        data={"document_type": document_type},
        files={"file": (filename, PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()

