from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.models import RefreshSession

SIGNUP_PAYLOAD = {
    "email": "refresh-user@acme.example.com",
    "password": "correct horse battery staple",
    "full_name": "Refresh User",
    "company_name": "Acme Contracting",
}

COOKIE = settings.refresh_cookie_name


def _signup(client: TestClient) -> str:
    response = client.post("/v1/auth/signup", json=SIGNUP_PAYLOAD)
    assert response.status_code == 201
    return response.cookies[COOKIE]


def test_refresh_succeeds_and_issues_a_new_access_token(client: TestClient) -> None:
    _signup(client)

    response = client.post("/v1/auth/refresh")

    assert response.status_code == 200
    assert "access_token" in response.json()


def test_refresh_rotates_the_refresh_token(client: TestClient) -> None:
    original_token = _signup(client)

    response = client.post("/v1/auth/refresh")

    new_token = response.cookies[COOKIE]
    assert new_token != original_token


def test_old_refresh_token_cannot_be_reused_after_rotation(
    client: TestClient, db_session: Session
) -> None:
    original_token = _signup(client)

    first_refresh = client.post("/v1/auth/refresh")
    assert first_refresh.status_code == 200

    # present the ORIGINAL (now-rotated-out) token again
    client.cookies.set(COOKIE, original_token)
    reuse_attempt = client.post("/v1/auth/refresh")

    assert reuse_attempt.status_code == 401
    assert reuse_attempt.json()["error"]["code"] == "invalid_refresh_token"


def test_refresh_token_reuse_revokes_the_whole_family(
    client: TestClient, db_session: Session
) -> None:
    original_token = _signup(client)
    rotated = client.post("/v1/auth/refresh")
    new_token = rotated.cookies[COOKIE]

    # reuse of the old token is a signal of compromise -- the new
    # (legitimate) token must also stop working
    client.cookies.set(COOKIE, original_token)
    client.post("/v1/auth/refresh")

    client.cookies.set(COOKIE, new_token)
    second_use_of_new_token = client.post("/v1/auth/refresh")

    assert second_use_of_new_token.status_code == 401
    sessions = db_session.execute(select(RefreshSession)).scalars().all()
    assert all(s.revoked_at is not None for s in sessions)


def test_revoked_refresh_token_cannot_be_reused(client: TestClient) -> None:
    token = _signup(client)

    client.cookies.set(COOKIE, token)
    logout_response = client.post("/v1/auth/logout")
    assert logout_response.status_code == 204

    client.cookies.set(COOKIE, token)
    reuse_attempt = client.post("/v1/auth/refresh")

    assert reuse_attempt.status_code == 401
    assert reuse_attempt.json()["error"]["code"] == "invalid_refresh_token"


def test_logout_revokes_the_refresh_session(client: TestClient, db_session: Session) -> None:
    token = _signup(client)

    client.post("/v1/auth/logout")

    session = db_session.execute(
        select(RefreshSession).where(RefreshSession.token_hash == _hash(token))
    ).scalar_one()
    assert session.revoked_at is not None


def test_logout_without_a_session_is_a_harmless_no_op(client: TestClient) -> None:
    response = client.post("/v1/auth/logout")

    assert response.status_code == 204


def test_refresh_without_a_cookie_is_rejected(client: TestClient) -> None:
    response = client.post("/v1/auth/refresh")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_refresh_token"


def _hash(raw_token: str) -> str:
    from app.core.security import hash_refresh_token

    return hash_refresh_token(raw_token)

