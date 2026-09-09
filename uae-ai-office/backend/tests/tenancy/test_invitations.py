"""Team invitations: creation, delivery reporting, resend, revoke and
acceptance.

The delivery assertions here exist because of a specific failure mode
this feature is designed against: an application that reports "invitation
sent" for a message no provider ever accepted. The contract these tests
pin down is that the HTTP result describes the *invitation*, while
`email_delivery.status` -- and only that field -- describes the *email*.
A deployment with no mail credentials still issues a usable invite_url;
it just never claims anything was emailed.
"""

import uuid

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import factory as email_factory
from app.core.email.exceptions import EmailAuthenticationError
from app.core.email.provider import EmailMessage, EmailProvider, EmailSendResult
from app.core.security import create_access_token, hash_password
from app.db.session import set_company_context
from app.modules.auth.models import User
from app.modules.tenancy.models import CompanyInvitation, CompanyMember


def _signup(client: TestClient, email: str, company_name: str = "Invite Test Co") -> tuple[str, dict]:
    response = client.post(
        "/v1/auth/signup",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "full_name": "Owner User",
            "company_name": company_name,
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    return token, claims


def _seed_member(db_session: Session, *, company_id: uuid.UUID, email: str, role: str) -> str:
    user = User(email=email, password_hash=hash_password("irrelevant-password-value"), full_name="Seeded User")
    db_session.add(user)
    db_session.flush()
    set_company_context(db_session, company_id)
    db_session.add(CompanyMember(company_id=company_id, user_id=user.id, role=role))
    db_session.flush()
    return create_access_token(user_id=user.id, company_id=company_id, role=role)


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class _RecordingProvider(EmailProvider):
    name = "recording"

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> EmailSendResult:
        self.sent.append(message)
        return EmailSendResult(provider=self.name, provider_message_id="msg-1")


class _RejectingProvider(EmailProvider):
    name = "rejecting"

    def send(self, message: EmailMessage) -> EmailSendResult:
        raise EmailAuthenticationError("The provider rejected the configured credential.")


@pytest.fixture()
def unconfigured_email(monkeypatch: pytest.MonkeyPatch):
    """The default state of a deployment that has not been given mail
    credentials yet -- the exact situation this feature must survive.
    """
    monkeypatch.setattr(settings, "email_provider", None)
    email_factory.reset_email_provider_cache()
    yield
    email_factory.reset_email_provider_cache()


@pytest.fixture()
def sending_email(monkeypatch: pytest.MonkeyPatch) -> _RecordingProvider:
    provider = _RecordingProvider()
    monkeypatch.setattr(email_factory, "_provider", provider)
    yield provider
    email_factory.reset_email_provider_cache()


@pytest.fixture()
def failing_email(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(email_factory, "_provider", _RejectingProvider())
    yield
    email_factory.reset_email_provider_cache()


# --- Creation and delivery reporting ---


def test_invitation_is_created_and_link_returned_when_email_unconfigured(
    client: TestClient, unconfigured_email
):
    token, _ = _signup(client, "owner-inv1@example.com")

    response = client.post(
        "/v1/companies/current/invitations",
        json={"email": "newmember@example.com", "role": "member"},
        headers=_auth_header(token),
    )

    assert response.status_code == 201
    body = response.json()
    # The invitation itself succeeded -- losing it because mail is not
    # configured is the regression this asserts against.
    assert body["status"] == "pending"
    assert body["token"]
    assert body["invite_url"].endswith(f"/invite/{body['token']}")
    # ...but nothing may claim an email went out.
    assert body["email_delivery"]["status"] == "not_configured"
    assert body["email_delivery"]["provider"] is None


def test_invitation_reports_sent_only_when_a_provider_accepted_it(
    client: TestClient, sending_email: _RecordingProvider
):
    token, _ = _signup(client, "owner-inv2@example.com")

    response = client.post(
        "/v1/companies/current/invitations",
        json={"email": "invited@example.com", "role": "manager"},
        headers=_auth_header(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email_delivery"]["status"] == "sent"
    assert body["email_delivery"]["provider"] == "recording"
    assert len(sending_email.sent) == 1
    message = sending_email.sent[0]
    assert message.to_address == "invited@example.com"
    # The accept link must be in both bodies -- a plaintext-only client
    # that cannot see the HTML button still has to be able to join.
    assert body["token"] in message.html_body
    assert body["token"] in message.text_body


def test_provider_rejection_is_reported_as_failed_not_as_sent(client: TestClient, failing_email):
    token, _ = _signup(client, "owner-inv3@example.com")

    response = client.post(
        "/v1/companies/current/invitations",
        json={"email": "unreachable@example.com", "role": "member"},
        headers=_auth_header(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email_delivery"]["status"] == "failed"
    assert body["email_delivery"]["detail"]
    # The invitation survives the provider failure so it can be retried.
    assert body["status"] == "pending"


def test_invitation_email_outcome_is_recorded_in_the_audit_log(
    client: TestClient, unconfigured_email
):
    token, _ = _signup(client, "owner-inv4@example.com")
    client.post(
        "/v1/companies/current/invitations",
        json={"email": "audited@example.com", "role": "member"},
        headers=_auth_header(token),
    )

    entries = client.get("/v1/audit-logs", headers=_auth_header(token)).json()["items"]
    invitation_events = [e for e in entries if e["action"] == "tenancy.invitation_sent"]
    assert len(invitation_events) == 1
    # The audit log has to be able to answer "did this actually go out?"
    assert invitation_events[0]["metadata"]["email_delivery_status"] == "not_configured"


# --- Roles ---


def test_invitations_cannot_grant_owner_access(client: TestClient, unconfigured_email):
    token, _ = _signup(client, "owner-inv5@example.com")
    response = client.post(
        "/v1/companies/current/invitations",
        json={"email": "escalate@example.com", "role": "owner"},
        headers=_auth_header(token),
    )
    assert response.status_code == 403


def test_member_cannot_invite(client: TestClient, db_session: Session, unconfigured_email):
    _, claims = _signup(client, "owner-inv6@example.com")
    member_token = _seed_member(
        db_session, company_id=uuid.UUID(claims["company_id"]), email="m-inv6@example.com", role="member"
    )
    response = client.post(
        "/v1/companies/current/invitations",
        json={"email": "someone@example.com", "role": "member"},
        headers=_auth_header(member_token),
    )
    assert response.status_code == 403


def test_duplicate_pending_invitation_is_rejected(client: TestClient, unconfigured_email):
    token, _ = _signup(client, "owner-inv7@example.com")
    payload = {"email": "dupe@example.com", "role": "member"}
    assert client.post("/v1/companies/current/invitations", json=payload, headers=_auth_header(token)).status_code == 201
    second = client.post("/v1/companies/current/invitations", json=payload, headers=_auth_header(token))
    assert second.status_code == 409


# --- Resend and revoke ---


def test_resend_supersedes_the_previous_token(client: TestClient, unconfigured_email):
    token, _ = _signup(client, "owner-inv8@example.com")
    first = client.post(
        "/v1/companies/current/invitations",
        json={"email": "resend@example.com", "role": "member"},
        headers=_auth_header(token),
    ).json()

    second = client.post(
        f"/v1/companies/current/invitations/{first['id']}/resend",
        headers=_auth_header(token),
    )
    assert second.status_code == 200
    assert second.json()["token"] != first["token"]

    # The superseded link must stop working, or a resend would leave two
    # live invitations for one seat.
    stale = client.post(
        f"/v1/auth/invitations/{first['token']}/accept",
        json={"password": "correct horse battery staple", "full_name": "Stale User"},
    )
    assert stale.status_code == 400


def test_revoked_invitation_cannot_be_accepted(client: TestClient, unconfigured_email):
    token, _ = _signup(client, "owner-inv9@example.com")
    invitation = client.post(
        "/v1/companies/current/invitations",
        json={"email": "revoked@example.com", "role": "member"},
        headers=_auth_header(token),
    ).json()

    assert client.delete(
        f"/v1/companies/current/invitations/{invitation['id']}", headers=_auth_header(token)
    ).status_code == 204

    response = client.post(
        f"/v1/auth/invitations/{invitation['token']}/accept",
        json={"password": "correct horse battery staple", "full_name": "Revoked User"},
    )
    assert response.status_code == 400


# --- Acceptance ---


def test_accepting_an_invitation_joins_the_company_with_the_invited_role(
    client: TestClient, db_session: Session, unconfigured_email
):
    token, claims = _signup(client, "owner-inv10@example.com")
    company_id = uuid.UUID(claims["company_id"])
    invitation = client.post(
        "/v1/companies/current/invitations",
        json={"email": "joiner@example.com", "role": "manager"},
        headers=_auth_header(token),
    ).json()

    response = client.post(
        f"/v1/auth/invitations/{invitation['token']}/accept",
        json={"password": "correct horse battery staple", "full_name": "Joiner User"},
    )
    assert response.status_code == 200

    members = client.get("/v1/companies/current/members", headers=_auth_header(token)).json()
    joined = [m for m in members if m["email"] == "joiner@example.com"]
    assert len(joined) == 1
    assert joined[0]["role"] == "manager"

    set_company_context(db_session, company_id)
    row = db_session.execute(
        select(CompanyInvitation).where(CompanyInvitation.id == uuid.UUID(invitation["id"]))
    ).scalar_one()
    assert row.accepted_at is not None


def test_an_invitation_token_cannot_be_used_twice(client: TestClient, unconfigured_email):
    token, _ = _signup(client, "owner-inv11@example.com")
    invitation = client.post(
        "/v1/companies/current/invitations",
        json={"email": "twice@example.com", "role": "member"},
        headers=_auth_header(token),
    ).json()
    body = {"password": "correct horse battery staple", "full_name": "Twice User"}

    assert client.post(f"/v1/auth/invitations/{invitation['token']}/accept", json=body).status_code == 200
    assert client.post(f"/v1/auth/invitations/{invitation['token']}/accept", json=body).status_code == 400


# ---------------------------------------------------------------------
# Accepting into an account that already exists.
#
# Accepting an invitation issues a full session for the invited address.
# When no account exists yet that is safe: the link is the only claim to
# the address and the accepter chooses the password. When an account
# already exists it is not, because the raw token is not a secret held
# only by the recipient -- an owner/admin invites any address they like
# and reads the token straight out of the 201 response. Without a
# password check, that is a login as somebody else's existing account,
# and /auth/me/companies/switch then reaches every other company that
# account belongs to. These tests pin the check that closes it.
# ---------------------------------------------------------------------


def _existing_account(db_session: Session, email: str, password: str) -> uuid.UUID:
    user = User(email=email, password_hash=hash_password(password), full_name="Existing Person")
    db_session.add(user)
    db_session.flush()
    return user.id


def test_invitation_cannot_take_over_an_existing_account_without_its_password(
    client: TestClient, db_session: Session, unconfigured_email
):
    victim_email = "victim-existing@example.com"
    _existing_account(db_session, victim_email, "the victims real password")

    token, _ = _signup(client, "attacker-owner@example.com")
    invitation = client.post(
        "/v1/companies/current/invitations",
        json={"email": victim_email, "role": "member"},
        headers=_auth_header(token),
    ).json()

    # The inviter holds the raw token and tries to accept it themselves.
    response = client.post(
        f"/v1/auth/invitations/{invitation['token']}/accept",
        json={"password": "not the victims password", "full_name": "Attacker"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invitation_existing_account"
    # No session was handed out, and no membership was granted.
    assert settings.refresh_cookie_name not in response.cookies
    members = client.get("/v1/companies/current/members", headers=_auth_header(token)).json()
    assert [m for m in members if m["email"] == victim_email] == []


def test_existing_account_joins_when_it_supplies_its_own_password(
    client: TestClient, db_session: Session, unconfigured_email
):
    joiner_email = "existing-joiner@example.com"
    password = "the joiners real password"
    _existing_account(db_session, joiner_email, password)

    token, _ = _signup(client, "owner-existing-join@example.com")
    invitation = client.post(
        "/v1/companies/current/invitations",
        json={"email": joiner_email, "role": "manager"},
        headers=_auth_header(token),
    ).json()

    response = client.post(
        f"/v1/auth/invitations/{invitation['token']}/accept",
        json={"password": password},
    )

    assert response.status_code == 200
    members = client.get("/v1/companies/current/members", headers=_auth_header(token)).json()
    joined = [m for m in members if m["email"] == joiner_email]
    assert len(joined) == 1
    assert joined[0]["role"] == "manager"
    # An invitation must not rewrite the profile of an account that
    # already existed, even when the accept body carries a name.
    assert joined[0]["full_name"] == "Existing Person"


def test_accept_does_not_rename_an_existing_account(
    client: TestClient, db_session: Session, unconfigured_email
):
    email = "rename-target@example.com"
    password = "another real password here"
    user_id = _existing_account(db_session, email, password)

    token, _ = _signup(client, "owner-rename@example.com")
    invitation = client.post(
        "/v1/companies/current/invitations",
        json={"email": email, "role": "member"},
        headers=_auth_header(token),
    ).json()

    assert client.post(
        f"/v1/auth/invitations/{invitation['token']}/accept",
        json={"password": password, "full_name": "Renamed By Invitation"},
    ).status_code == 200

    assert db_session.get(User, user_id).full_name == "Existing Person"


def test_preview_tells_the_client_which_password_to_ask_for(
    client: TestClient, db_session: Session, unconfigured_email
):
    existing_email = "preview-existing@example.com"
    _existing_account(db_session, existing_email, "some real password here")

    token, _ = _signup(client, "owner-preview@example.com", company_name="Preview Co")
    new_invitation = client.post(
        "/v1/companies/current/invitations",
        json={"email": "preview-new@example.com", "role": "member"},
        headers=_auth_header(token),
    ).json()
    existing_invitation = client.post(
        "/v1/companies/current/invitations",
        json={"email": existing_email, "role": "manager"},
        headers=_auth_header(token),
    ).json()

    # Unauthenticated: the link holder is exactly who this serves.
    new_preview = client.get(f"/v1/auth/invitations/{new_invitation['token']}")
    assert new_preview.status_code == 200
    assert new_preview.json()["requires_existing_password"] is False
    assert new_preview.json()["company_name"] == "Preview Co"
    assert new_preview.json()["role"] == "member"

    existing_preview = client.get(f"/v1/auth/invitations/{existing_invitation['token']}")
    assert existing_preview.status_code == 200
    assert existing_preview.json()["requires_existing_password"] is True


def test_preview_of_an_unusable_token_reveals_nothing(client: TestClient, unconfigured_email):
    token, _ = _signup(client, "owner-preview2@example.com")
    invitation = client.post(
        "/v1/companies/current/invitations",
        json={"email": "revoked-preview@example.com", "role": "member"},
        headers=_auth_header(token),
    ).json()
    client.delete(
        f"/v1/companies/current/invitations/{invitation['id']}", headers=_auth_header(token)
    )

    revoked = client.get(f"/v1/auth/invitations/{invitation['token']}")
    unknown = client.get(f"/v1/auth/invitations/{'0' * 43}")

    # A revoked token and a token that never existed are indistinguishable.
    assert revoked.status_code == unknown.status_code == 400
    assert revoked.json()["error"]["code"] == unknown.json()["error"]["code"] == "invitation_invalid"


def test_new_account_still_requires_a_full_name(client: TestClient, unconfigured_email):
    token, _ = _signup(client, "owner-noname@example.com")
    invitation = client.post(
        "/v1/companies/current/invitations",
        json={"email": "noname@example.com", "role": "member"},
        headers=_auth_header(token),
    ).json()

    response = client.post(
        f"/v1/auth/invitations/{invitation['token']}/accept",
        json={"password": "correct horse battery staple"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invitation_invalid"
