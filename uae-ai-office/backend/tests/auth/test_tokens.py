from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from app.core.config import settings

SIGNUP_PAYLOAD = {
    "email": "token-user@acme.example.com",
    "password": "correct horse battery staple",
    "full_name": "Token User",
    "company_name": "Acme Contracting",
}


def _signup_and_get_access_token(client: TestClient) -> str:
    response = client.post("/v1/auth/signup", json=SIGNUP_PAYLOAD)
    assert response.status_code == 201
    return response.json()["access_token"]


def test_access_token_contains_only_expected_minimal_claims(client: TestClient) -> None:
    token = _signup_and_get_access_token(client)

    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

    assert set(payload.keys()) == {"sub", "company_id", "role", "type", "iat", "exp"}
    assert payload["type"] == "access"
    assert payload["role"] == "owner"
    # nothing personally identifying beyond the opaque user id
    assert "email" not in payload
    assert "full_name" not in payload
    assert "password" not in payload


def test_expired_access_token_is_rejected(client: TestClient) -> None:
    token = _signup_and_get_access_token(client)
    claims = jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    now = datetime.now(UTC)
    expired_claims = {**claims, "iat": now - timedelta(minutes=30), "exp": now - timedelta(minutes=15)}
    expired_token = jwt.encode(expired_claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    response = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_malformed_token_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/v1/auth/me", headers={"Authorization": "Bearer not-a-real-jwt-at-all"}
    )

    assert response.status_code == 401


def test_token_with_wrong_signature_is_rejected(client: TestClient) -> None:
    token = _signup_and_get_access_token(client)
    claims = jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    forged_token = jwt.encode(
        claims, "a-completely-different-secret-of-sufficient-length", algorithm=settings.jwt_algorithm
    )

    response = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {forged_token}"})

    assert response.status_code == 401

