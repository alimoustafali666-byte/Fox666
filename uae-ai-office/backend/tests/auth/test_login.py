from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.models import User

SIGNUP_PAYLOAD = {
    "email": "login-user@acme.example.com",
    "password": "correct horse battery staple",
    "full_name": "Login User",
    "company_name": "Acme Contracting",
}


def _signup(client: TestClient) -> None:
    response = client.post("/v1/auth/signup", json=SIGNUP_PAYLOAD)
    assert response.status_code == 201


def test_correct_login_succeeds(client: TestClient) -> None:
    _signup(client)

    response = client.post(
        "/v1/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert settings.refresh_cookie_name in response.cookies


def test_wrong_password_fails_generically(client: TestClient) -> None:
    _signup(client)

    response = client.post(
        "/v1/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": "totally-wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_nonexistent_email_fails_generically(client: TestClient) -> None:
    response = client.post(
        "/v1/auth/login",
        json={"email": "nobody-here@acme.example.com", "password": "whatever-password-123"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "invalid_credentials"


def test_wrong_password_and_nonexistent_email_return_identical_responses(
    client: TestClient,
) -> None:
    """The response body/status must not let a caller distinguish "email
    exists, password wrong" from "email doesn't exist".
    """
    _signup(client)

    wrong_password = client.post(
        "/v1/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": "totally-wrong-password"},
    )
    unknown_email = client.post(
        "/v1/auth/login",
        json={"email": "nobody-here@acme.example.com", "password": "totally-wrong-password"},
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_inactive_user_cannot_authenticate(client: TestClient, db_session: Session) -> None:
    _signup(client)
    db_session.execute(
        update(User).where(User.email == SIGNUP_PAYLOAD["email"]).values(is_active=False)
    )
    db_session.flush()

    response = client.post(
        "/v1/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_repeated_failed_logins_are_rate_limited(client: TestClient) -> None:
    _signup(client)
    bad_login = {"email": SIGNUP_PAYLOAD["email"], "password": "wrong-password"}

    for _ in range(settings.login_rate_limit_max_attempts):
        response = client.post("/v1/auth/login", json=bad_login)
        assert response.status_code == 401

    locked_response = client.post("/v1/auth/login", json=bad_login)

    assert locked_response.status_code == 429
    assert locked_response.json()["error"]["code"] == "too_many_attempts"


def test_successful_login_resets_rate_limit_counter(client: TestClient) -> None:
    _signup(client)
    bad_login = {"email": SIGNUP_PAYLOAD["email"], "password": "wrong-password"}
    good_login = {"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]}

    for _ in range(settings.login_rate_limit_max_attempts - 1):
        client.post("/v1/auth/login", json=bad_login)

    assert client.post("/v1/auth/login", json=good_login).status_code == 200
    # counter reset by the success, so a fresh run of failures doesn't
    # immediately lock out
    assert client.post("/v1/auth/login", json=bad_login).status_code == 401


def test_last_login_at_updated_on_success(client: TestClient, db_session: Session) -> None:
    _signup(client)

    client.post(
        "/v1/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]},
    )

    user = db_session.execute(
        select(User).where(User.email == SIGNUP_PAYLOAD["email"])
    ).scalar_one()
    assert user.last_login_at is not None

