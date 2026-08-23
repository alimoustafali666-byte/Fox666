import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import set_company_context
from app.modules.audit_log.models import AuditLog

SIGNUP_PAYLOAD = {
    "email": "audit-user@acme.example.com",
    "password": "correct horse battery staple",
    "full_name": "Audit User",
    "company_name": "Acme Contracting",
}


def _actions_for(db_session: Session, company_id: uuid.UUID) -> list[str]:
    set_company_context(db_session, company_id)
    rows = db_session.execute(
        select(AuditLog.action).order_by(AuditLog.created_at.asc())
    ).scalars()
    return list(rows)


def _company_id_from_token(access_token: str) -> uuid.UUID:
    claims = jwt.decode(
        access_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    return uuid.UUID(claims["company_id"])


def test_signup_writes_an_audit_event(client: TestClient, db_session: Session) -> None:
    response = client.post("/v1/auth/signup", json=SIGNUP_PAYLOAD)
    company_id = _company_id_from_token(response.json()["access_token"])

    assert "auth.signup" in _actions_for(db_session, company_id)


def test_login_success_and_failure_write_audit_events(
    client: TestClient, db_session: Session
) -> None:
    signup_response = client.post("/v1/auth/signup", json=SIGNUP_PAYLOAD)
    company_id = _company_id_from_token(signup_response.json()["access_token"])

    client.post(
        "/v1/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": "wrong-password"},
    )
    client.post(
        "/v1/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]},
    )

    actions = _actions_for(db_session, company_id)
    assert "auth.login_failure" in actions
    assert "auth.login_success" in actions


def test_login_failure_for_unknown_email_writes_no_audit_row_anywhere(
    client: TestClient, db_session: Session
) -> None:
    """There is no company to attribute an unknown-email attempt to
    (audit_logs is company-scoped) -- this is the documented "where
    safely attributable" limit, not a bug.
    """
    client.post(
        "/v1/auth/login",
        json={"email": "no-such-account@acme.example.com", "password": "whatever-123"},
    )

    set_company_context(db_session, None)
    rows = db_session.execute(select(AuditLog)).scalars().all()
    assert all(
        (row.metadata_ or {}).get("email") != "no-such-account@acme.example.com" for row in rows
    )


def test_logout_writes_an_audit_event(client: TestClient, db_session: Session) -> None:
    signup_response = client.post("/v1/auth/signup", json=SIGNUP_PAYLOAD)
    company_id = _company_id_from_token(signup_response.json()["access_token"])
    client.post("/v1/auth/logout")

    assert "auth.logout" in _actions_for(db_session, company_id)


def test_refresh_reuse_writes_a_security_audit_event(
    client: TestClient, db_session: Session
) -> None:
    signup_response = client.post("/v1/auth/signup", json=SIGNUP_PAYLOAD)
    company_id = _company_id_from_token(signup_response.json()["access_token"])
    original_token = signup_response.cookies[settings.refresh_cookie_name]

    client.post("/v1/auth/refresh")  # rotates
    client.cookies.set(settings.refresh_cookie_name, original_token)
    client.post("/v1/auth/refresh")  # reuse

    assert "auth.refresh_reuse_detected" in _actions_for(db_session, company_id)

