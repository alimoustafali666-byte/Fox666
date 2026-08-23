"""Step 20 -- company administration: company info edit, logo upload/
download/delete, member role change, member removal. Reuses the same
file-local signup/seed-member/auth-header helper convention as
test_rbac.py (this module's existing pattern) rather than a shared
helpers.py.
"""

import base64
import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import set_company_context
from app.modules.auth.models import User
from app.modules.tenancy.models import CompanyMember

# A genuine 1x1 transparent PNG (structurally valid, passes magic-byte
# sniffing) -- not a placeholder string.
_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
_JPEG_MAGIC_ONLY = b"\xff\xd8\xff\xe0" + b"\x00" * 64  # not a structurally valid JPEG


def _signup(client: TestClient, email: str, company_name: str = "Admin Test Co") -> tuple[str, dict]:
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


def _seed_member(db_session: Session, *, company_id: uuid.UUID, email: str, role: str) -> tuple[str, uuid.UUID]:
    user = User(email=email, password_hash=hash_password("irrelevant-password-value"), full_name="Seeded User")
    db_session.add(user)
    db_session.flush()

    set_company_context(db_session, company_id)
    db_session.add(CompanyMember(company_id=company_id, user_id=user.id, role=role))
    db_session.flush()

    return create_access_token(user_id=user.id, company_id=company_id, role=role), user.id


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- Company info ---


def test_owner_can_update_company_info(client: TestClient):
    token, _ = _signup(client, "owner1@example.com")
    resp = client.patch(
        "/v1/companies/current",
        json={"name": "Renamed Co", "timezone": "Europe/London", "country": "GB"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["company"]["name"] == "Renamed Co"
    assert body["company"]["timezone"] == "Europe/London"
    assert body["company"]["country"] == "GB"


def test_member_cannot_update_company_info(client: TestClient, db_session: Session):
    _, claims = _signup(client, "owner2@example.com")
    company_id = uuid.UUID(claims["company_id"])
    member_token, _ = _seed_member(db_session, company_id=company_id, email="member2@example.com", role="member")

    resp = client.patch(
        "/v1/companies/current", json={"name": "Hacked Co"}, headers=_auth_header(member_token)
    )
    assert resp.status_code == 403


def test_partial_update_only_touches_given_fields(client: TestClient):
    token, _ = _signup(client, "owner3@example.com")
    before = client.get("/v1/companies/current", headers=_auth_header(token)).json()["company"]

    resp = client.patch("/v1/companies/current", json={"name": "Only Name Changed"}, headers=_auth_header(token))
    assert resp.status_code == 200
    after = resp.json()["company"]
    assert after["name"] == "Only Name Changed"
    assert after["timezone"] == before["timezone"]
    assert after["country"] == before["country"]


# --- Logo ---


def test_owner_can_upload_and_retrieve_logo(client: TestClient):
    token, _ = _signup(client, "owner4@example.com")
    resp = client.post(
        "/v1/companies/current/logo",
        headers=_auth_header(token),
        files={"file": ("logo.png", _PNG_BYTES, "image/png")},
    )
    assert resp.status_code == 200
    assert resp.json()["has_logo"] is True

    current = client.get("/v1/companies/current", headers=_auth_header(token)).json()
    assert current["company"]["has_logo"] is True

    logo_resp = client.get("/v1/companies/current/logo", headers=_auth_header(token))
    assert logo_resp.status_code == 200
    assert logo_resp.headers["content-type"] == "image/png"
    assert logo_resp.content == _PNG_BYTES


def test_member_can_view_logo_but_not_upload(client: TestClient, db_session: Session):
    owner_token, claims = _signup(client, "owner5@example.com")
    company_id = uuid.UUID(claims["company_id"])
    member_token, _ = _seed_member(db_session, company_id=company_id, email="member5@example.com", role="member")

    client.post(
        "/v1/companies/current/logo",
        headers=_auth_header(owner_token),
        files={"file": ("logo.png", _PNG_BYTES, "image/png")},
    )

    upload_resp = client.post(
        "/v1/companies/current/logo",
        headers=_auth_header(member_token),
        files={"file": ("logo.png", _PNG_BYTES, "image/png")},
    )
    assert upload_resp.status_code == 403

    view_resp = client.get("/v1/companies/current/logo", headers=_auth_header(member_token))
    assert view_resp.status_code == 200
    assert view_resp.content == _PNG_BYTES


def test_no_logo_returns_404(client: TestClient):
    token, _ = _signup(client, "owner6@example.com")
    resp = client.get("/v1/companies/current/logo", headers=_auth_header(token))
    assert resp.status_code == 404


def test_logo_rejects_non_image_content(client: TestClient):
    token, _ = _signup(client, "owner7@example.com")
    resp = client.post(
        "/v1/companies/current/logo",
        headers=_auth_header(token),
        files={"file": ("logo.png", b"<script>alert(1)</script>", "image/png")},
    )
    assert resp.status_code == 400


def test_logo_rejects_content_mismatched_with_extension(client: TestClient):
    """A renamed file (real bytes don't match the claimed .png
    extension) is rejected -- the client-declared content-type/extension
    is never trusted alone, same discipline as document uploads."""
    token, _ = _signup(client, "owner7b@example.com")
    resp = client.post(
        "/v1/companies/current/logo",
        headers=_auth_header(token),
        files={"file": ("logo.png", _JPEG_MAGIC_ONLY, "image/png")},
    )
    assert resp.status_code == 400


def test_logo_rejects_oversized_upload(client: TestClient):
    token, _ = _signup(client, "owner8@example.com")
    oversized = _PNG_BYTES + b"\x00" * (2 * 1024 * 1024 + 1)
    resp = client.post(
        "/v1/companies/current/logo",
        headers=_auth_header(token),
        files={"file": ("logo.png", oversized, "image/png")},
    )
    assert resp.status_code == 400


def test_owner_can_delete_logo(client: TestClient):
    token, _ = _signup(client, "owner9@example.com")
    client.post(
        "/v1/companies/current/logo",
        headers=_auth_header(token),
        files={"file": ("logo.png", _PNG_BYTES, "image/png")},
    )
    del_resp = client.delete("/v1/companies/current/logo", headers=_auth_header(token))
    assert del_resp.status_code == 200
    assert del_resp.json()["has_logo"] is False

    get_resp = client.get("/v1/companies/current/logo", headers=_auth_header(token))
    assert get_resp.status_code == 404


def test_logo_is_tenant_isolated(client: TestClient):
    """Company A's logo is never visible under company B's tenant
    context, even though both hit the identical /companies/current/logo
    endpoint -- the company scoping comes from the caller's own JWT-
    resolved TenantContext, never a client-suppliable parameter."""
    token_a, _ = _signup(client, "ownerA@example.com", company_name="Company A")
    token_b, _ = _signup(client, "ownerB@example.com", company_name="Company B")

    client.post(
        "/v1/companies/current/logo",
        headers=_auth_header(token_a),
        files={"file": ("logo.png", _PNG_BYTES, "image/png")},
    )

    b_logo_resp = client.get("/v1/companies/current/logo", headers=_auth_header(token_b))
    assert b_logo_resp.status_code == 404

    b_current = client.get("/v1/companies/current", headers=_auth_header(token_b)).json()
    assert b_current["company"]["has_logo"] is False


# --- Member role changes ---


def test_owner_can_promote_member_to_manager(client: TestClient, db_session: Session):
    owner_token, claims = _signup(client, "owner10@example.com")
    company_id = uuid.UUID(claims["company_id"])
    _, member_id = _seed_member(db_session, company_id=company_id, email="member10@example.com", role="member")

    resp = client.patch(
        f"/v1/companies/current/members/{member_id}", json={"role": "manager"}, headers=_auth_header(owner_token)
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "manager"


def test_invalid_role_rejected(client: TestClient, db_session: Session):
    owner_token, claims = _signup(client, "owner11@example.com")
    company_id = uuid.UUID(claims["company_id"])
    _, member_id = _seed_member(db_session, company_id=company_id, email="member11@example.com", role="member")

    resp = client.patch(
        f"/v1/companies/current/members/{member_id}",
        json={"role": "superadmin"},
        headers=_auth_header(owner_token),
    )
    assert resp.status_code == 400


def test_admin_cannot_change_owner_role(client: TestClient, db_session: Session):
    owner_token, claims = _signup(client, "owner12@example.com")
    company_id = uuid.UUID(claims["company_id"])
    admin_token, _ = _seed_member(db_session, company_id=company_id, email="admin12@example.com", role="admin")

    # Find the original owner's user_id via the members list (owner endpoint).
    members = client.get("/v1/companies/current/members", headers=_auth_header(owner_token)).json()
    owner_member = next(m for m in members if m["role"] == "owner")

    resp = client.patch(
        f"/v1/companies/current/members/{owner_member['user_id']}",
        json={"role": "manager"},
        headers=_auth_header(admin_token),
    )
    assert resp.status_code == 403


def test_admin_cannot_promote_someone_to_owner(client: TestClient, db_session: Session):
    _, claims = _signup(client, "owner13@example.com")
    company_id = uuid.UUID(claims["company_id"])
    admin_token, _ = _seed_member(db_session, company_id=company_id, email="admin13@example.com", role="admin")
    _, member_id = _seed_member(db_session, company_id=company_id, email="member13@example.com", role="member")

    resp = client.patch(
        f"/v1/companies/current/members/{member_id}", json={"role": "owner"}, headers=_auth_header(admin_token)
    )
    assert resp.status_code == 403


def test_cannot_demote_last_owner(client: TestClient):
    owner_token, _ = _signup(client, "owner14@example.com")
    members = client.get("/v1/companies/current/members", headers=_auth_header(owner_token)).json()
    owner_member = next(m for m in members if m["role"] == "owner")

    resp = client.patch(
        f"/v1/companies/current/members/{owner_member['user_id']}",
        json={"role": "admin"},
        headers=_auth_header(owner_token),
    )
    assert resp.status_code == 400


def test_owner_can_demote_owner_when_a_second_owner_exists(client: TestClient, db_session: Session):
    owner_token, claims = _signup(client, "owner15@example.com")
    company_id = uuid.UUID(claims["company_id"])
    _, second_owner_id = _seed_member(
        db_session, company_id=company_id, email="owner15b@example.com", role="owner"
    )

    resp = client.patch(
        f"/v1/companies/current/members/{second_owner_id}",
        json={"role": "manager"},
        headers=_auth_header(owner_token),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "manager"


def test_forged_member_id_returns_404(client: TestClient):
    owner_token, _ = _signup(client, "owner16@example.com")
    fake_id = uuid.uuid4()
    resp = client.patch(
        f"/v1/companies/current/members/{fake_id}", json={"role": "admin"}, headers=_auth_header(owner_token)
    )
    assert resp.status_code == 404


def test_cross_company_member_id_returns_404(client: TestClient, db_session: Session):
    """A user_id that's real but belongs to a DIFFERENT company must be
    indistinguishable from a nonexistent one -- classic IDOR check."""
    owner_a_token, _ = _signup(client, "ownerA2@example.com", company_name="Company A2")
    _, claims_b = _signup(client, "ownerB2@example.com", company_name="Company B2")
    company_b_id = uuid.UUID(claims_b["company_id"])
    _, member_b_id = _seed_member(db_session, company_id=company_b_id, email="memberB2@example.com", role="member")

    resp = client.patch(
        f"/v1/companies/current/members/{member_b_id}",
        json={"role": "admin"},
        headers=_auth_header(owner_a_token),
    )
    assert resp.status_code == 404


# --- Member removal ---


def test_owner_can_remove_member(client: TestClient, db_session: Session):
    owner_token, claims = _signup(client, "owner17@example.com")
    company_id = uuid.UUID(claims["company_id"])
    _, member_id = _seed_member(db_session, company_id=company_id, email="member17@example.com", role="member")

    resp = client.delete(f"/v1/companies/current/members/{member_id}", headers=_auth_header(owner_token))
    assert resp.status_code == 204

    members = client.get("/v1/companies/current/members", headers=_auth_header(owner_token)).json()
    assert all(m["user_id"] != str(member_id) for m in members)


def test_cannot_remove_self(client: TestClient):
    owner_token, _ = _signup(client, "owner18@example.com")
    members = client.get("/v1/companies/current/members", headers=_auth_header(owner_token)).json()
    owner_member = next(m for m in members if m["role"] == "owner")

    resp = client.delete(
        f"/v1/companies/current/members/{owner_member['user_id']}", headers=_auth_header(owner_token)
    )
    assert resp.status_code == 400


def test_admin_cannot_remove_owner(client: TestClient, db_session: Session):
    owner_token, claims = _signup(client, "owner19@example.com")
    company_id = uuid.UUID(claims["company_id"])
    admin_token, _ = _seed_member(db_session, company_id=company_id, email="admin19@example.com", role="admin")

    members = client.get("/v1/companies/current/members", headers=_auth_header(owner_token)).json()
    owner_member = next(m for m in members if m["role"] == "owner")

    resp = client.delete(
        f"/v1/companies/current/members/{owner_member['user_id']}", headers=_auth_header(admin_token)
    )
    assert resp.status_code == 403


def test_member_cannot_remove_anyone(client: TestClient, db_session: Session):
    _, claims = _signup(client, "owner20@example.com")
    company_id = uuid.UUID(claims["company_id"])
    member_token, _ = _seed_member(db_session, company_id=company_id, email="member20a@example.com", role="member")
    _, other_member_id = _seed_member(db_session, company_id=company_id, email="member20b@example.com", role="member")

    resp = client.delete(
        f"/v1/companies/current/members/{other_member_id}", headers=_auth_header(member_token)
    )
    assert resp.status_code == 403


def test_direct_endpoint_access_without_authentication(client: TestClient):
    resp = client.patch("/v1/companies/current", json={"name": "x"})
    assert resp.status_code == 401
    resp = client.get("/v1/companies/current/logo")
    assert resp.status_code == 401
    resp = client.delete(f"/v1/companies/current/members/{uuid.uuid4()}")
    assert resp.status_code == 401

