from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import set_user_context
from app.modules.auth.models import User
from app.modules.auth.repository import get_own_memberships
from app.modules.tenancy.models import Company

SIGNUP_PAYLOAD = {
    "email": "owner@acme.example.com",
    "password": "correct horse battery staple",
    "full_name": "Ada Owner",
    "company_name": "Acme Contracting",
}


def test_signup_creates_user_company_and_owner_membership_atomically(
    client: TestClient, db_session: Session
) -> None:
    response = client.post("/v1/auth/signup", json=SIGNUP_PAYLOAD)

    assert response.status_code == 201
    assert "access_token" in response.json()

    user = db_session.execute(
        select(User).where(User.email == SIGNUP_PAYLOAD["email"])
    ).scalar_one()
    company = db_session.execute(
        select(Company).where(Company.name == SIGNUP_PAYLOAD["company_name"])
    ).scalar_one()

    set_user_context(db_session, user.id)
    memberships = get_own_memberships(db_session, user.id)

    assert len(memberships) == 1
    assert memberships[0].company_id == company.id
    assert memberships[0].role == "owner"
    assert company.timezone == "Asia/Dubai"
    assert company.country == "AE"


def test_signup_rejects_duplicate_email(client: TestClient, db_session: Session) -> None:
    first = client.post("/v1/auth/signup", json=SIGNUP_PAYLOAD)
    assert first.status_code == 201

    second_payload = {**SIGNUP_PAYLOAD, "company_name": "A Different Company"}
    second = client.post("/v1/auth/signup", json=second_payload)

    assert second.status_code == 409
    body = second.json()
    assert body["error"]["code"] == "email_already_registered"
    # must not leak anything about the existing account beyond "taken"
    assert "Ada Owner" not in str(body)
    assert "Acme Contracting" not in str(body)

    # and the failed second attempt must not have created a stray company
    stray = db_session.execute(
        select(Company).where(Company.name == "A Different Company")
    ).scalar_one_or_none()
    assert stray is None


def test_signup_stores_password_hashed_not_plaintext(
    client: TestClient, db_session: Session
) -> None:
    response = client.post("/v1/auth/signup", json=SIGNUP_PAYLOAD)
    assert response.status_code == 201

    user = db_session.execute(
        select(User).where(User.email == SIGNUP_PAYLOAD["email"])
    ).scalar_one()

    assert user.password_hash != SIGNUP_PAYLOAD["password"]
    assert user.password_hash.startswith("$argon2id$")


def test_signup_rejects_password_shorter_than_minimum(client: TestClient) -> None:
    short_password = "tooshort1"
    payload = {**SIGNUP_PAYLOAD, "email": "shortpw@acme.example.com", "password": short_password}

    response = client.post("/v1/auth/signup", json=payload)

    assert response.status_code == 422
    # regression check: FastAPI's default validation-error handler echoes
    # the raw submitted value back per-field, which would put a rejected
    # plaintext password straight into the response body -- our handler
    # must strip that.
    assert short_password not in response.text
    assert response.json()["error"]["code"] == "validation_error"

