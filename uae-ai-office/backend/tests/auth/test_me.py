from fastapi.testclient import TestClient

SIGNUP_PAYLOAD = {
    "email": "me-user@acme.example.com",
    "password": "correct horse battery staple",
    "full_name": "Me User",
    "company_name": "Acme Contracting",
}


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_me_returns_safe_fields_only(client: TestClient) -> None:
    signup = client.post("/v1/auth/signup", json=SIGNUP_PAYLOAD)
    token = signup.json()["access_token"]

    response = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == SIGNUP_PAYLOAD["email"]
    assert body["user"]["full_name"] == SIGNUP_PAYLOAD["full_name"]
    assert body["role"] == "owner"
    assert "company_id" in body

    body_text = str(body)
    for forbidden in ("password", "password_hash", "token_hash", "refresh_token"):
        assert forbidden not in body_text

