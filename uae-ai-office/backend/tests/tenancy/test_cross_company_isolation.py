import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import set_company_context, set_user_context
from app.modules.auth.repository import get_own_memberships
from app.modules.tenancy import repository as tenancy_repository
from app.modules.tenancy.models import CompanyMember


def _signup(client: TestClient, email: str, company_name: str) -> tuple[str, dict]:
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


# 13. Company A cannot read Company B tenant-owned rows through repository code
def test_repository_code_cannot_read_another_companys_members_even_if_asked(
    client: TestClient, db_session: Session
) -> None:
    _, claims_a = _signup(client, "iso-repo-a@example.com", "Company A")
    _, claims_b = _signup(client, "iso-repo-b@example.com", "Company B")
    company_a = uuid.UUID(claims_a["company_id"])
    company_b = uuid.UUID(claims_b["company_id"])

    # RLS context is set to company A, but the repository function is
    # called with company B's id -- if application code ever "forgot" to
    # trust the context and instead passed along some other company_id
    # (e.g. from a bug), RLS must still block it rather than the function
    # honoring whatever id it was given.
    set_company_context(db_session, company_a)
    rows = tenancy_repository.list_company_members_with_user_info(db_session, company_b)

    assert rows == []


# 14. Company A cannot read Company B rows through direct ORM query under RLS
def test_direct_orm_query_cannot_read_another_companys_members(
    client: TestClient, db_session: Session
) -> None:
    _, claims_a = _signup(client, "iso-orm-a@example.com", "Company A")
    _, claims_b = _signup(client, "iso-orm-b@example.com", "Company B")
    company_a = uuid.UUID(claims_a["company_id"])
    company_b = uuid.UUID(claims_b["company_id"])

    set_company_context(db_session, company_a)
    rows = db_session.execute(select(CompanyMember)).scalars().all()

    seen_company_ids = {row.company_id for row in rows}
    assert company_b not in seen_company_ids
    assert seen_company_ids == {company_a}


# 22. cross-company membership lookup exposes only the authenticated user's own memberships
def test_self_membership_lookup_never_exposes_another_users_memberships(
    client: TestClient, db_session: Session
) -> None:
    _, claims_a = _signup(client, "iso-self-a@example.com", "Company A")
    _, claims_b = _signup(client, "iso-self-b@example.com", "Company B")
    user_a = uuid.UUID(claims_a["sub"])
    user_b = uuid.UUID(claims_b["sub"])

    set_user_context(db_session, user_a)
    memberships_seen = get_own_memberships(db_session, user_a)

    assert {m.user_id for m in memberships_seen} == {user_a}
    assert user_b not in {m.user_id for m in memberships_seen}

    # and switching the user context to B must never leak A's row either
    set_user_context(db_session, user_b)
    memberships_for_b = get_own_memberships(db_session, user_b)
    assert {m.user_id for m in memberships_for_b} == {user_b}

