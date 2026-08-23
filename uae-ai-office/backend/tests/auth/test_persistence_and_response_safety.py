from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_refresh_token
from app.modules.auth.models import RefreshSession

SIGNUP_PAYLOAD = {
    "email": "safety-user@acme.example.com",
    "password": "correct horse battery staple",
    "full_name": "Safety User",
    "company_name": "Acme Contracting",
}


def test_raw_refresh_token_is_never_persisted(client: TestClient, db_session: Session) -> None:
    response = client.post("/v1/auth/signup", json=SIGNUP_PAYLOAD)
    raw_token = response.cookies[settings.refresh_cookie_name]

    session = db_session.execute(select(RefreshSession)).scalar_one()

    assert session.token_hash != raw_token
    assert session.token_hash == hash_refresh_token(raw_token)
    # sha256 hex digest -- not, say, the raw token truncated or encoded
    assert len(session.token_hash) == 64
    all(c in "0123456789abcdef" for c in session.token_hash)


def test_signup_response_never_includes_password_or_token_hashes(client: TestClient) -> None:
    response = client.post("/v1/auth/signup", json=SIGNUP_PAYLOAD)

    body_text = str(response.json())
    for forbidden in ("password", "password_hash", "token_hash"):
        assert forbidden not in body_text


def test_login_response_never_includes_password_or_token_hashes(client: TestClient) -> None:
    client.post("/v1/auth/signup", json=SIGNUP_PAYLOAD)

    response = client.post(
        "/v1/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]},
    )

    body_text = str(response.json())
    for forbidden in ("password", "password_hash", "token_hash"):
        assert forbidden not in body_text

