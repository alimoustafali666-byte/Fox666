import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import set_company_context
from app.modules.projects import repository as projects_repository
from app.modules.projects.models import Project
from tests.projects.helpers import auth_header, signup


def _create(client: TestClient, token: str, **kwargs) -> dict:
    payload = {"name": "Project"} | kwargs
    response = client.post("/v1/projects", json=payload, headers=auth_header(token))
    assert response.status_code == 201
    return response.json()


# 39. RLS independently blocks cross-company access
def test_rls_blocks_cross_company_reads_via_direct_orm_query(
    client: TestClient, db_session: Session
) -> None:
    token_a, claims_a = signup(client, "rls-iso-a@example.com", "Company A")
    token_b, _ = signup(client, "rls-iso-b@example.com", "Company B")
    _create(client, token_a, name="A's Project")
    _create(client, token_b, name="B's Project")

    company_a = uuid.UUID(claims_a["company_id"])
    set_company_context(db_session, company_a)
    rows = db_session.execute(select(Project)).scalars().all()

    assert {row.name for row in rows} == {"A's Project"}


def test_rls_blocks_repository_call_even_with_wrong_company_id_argument(
    client: TestClient, db_session: Session
) -> None:
    """Same defense-in-depth property already proven for tenancy/audit_log
    in earlier steps: even if the repository function were ever called
    with the wrong company_id (a bug), RLS still only returns rows
    matching the *active context*, never the parameter.
    """
    _, claims_a = signup(client, "rls-repo-a@example.com", "Company A")
    token_b, claims_b = signup(client, "rls-repo-b@example.com", "Company B")
    project_b = _create(client, token_b, name="B's Project")

    company_a = uuid.UUID(claims_a["company_id"])
    company_b = uuid.UUID(claims_b["company_id"])
    set_company_context(db_session, company_a)

    result = projects_repository.get_project_by_id(
        db_session, company_id=company_b, project_id=uuid.UUID(project_b["id"])
    )

    assert result is None


def test_missing_company_context_sees_no_projects(client: TestClient, db_session: Session) -> None:
    token, _ = signup(client, "rls-no-context@example.com")
    _create(client, token, name="Should Be Invisible")

    set_company_context(db_session, None)
    rows = db_session.execute(select(Project)).scalars().all()

    assert rows == []

