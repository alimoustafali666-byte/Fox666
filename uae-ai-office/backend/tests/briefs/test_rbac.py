import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.llm.fake_provider import FakeLLMProvider
from tests.briefs.helpers import get_brief, list_briefs, regenerate_brief
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.helpers import seed_member, signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes


def _seed_company_with_document(client: TestClient, email: str) -> tuple[str, uuid.UUID]:
    token, claims = signup(client, email)
    pdf_bytes = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])
    upload_process_and_index(client, token, filename="terms.pdf", content=pdf_bytes)
    return token, uuid.UUID(claims["company_id"])


# owner/admin/manager can trigger regeneration
def test_owner_admin_manager_can_regenerate(
    client: TestClient, fake_llm_provider: FakeLLMProvider, db_session: Session
) -> None:
    owner_token, company_id = _seed_company_with_document(client, "rbac-brief-owner@example.com")

    response = regenerate_brief(client, owner_token)
    assert response.status_code == 201, response.text

    for role in ("admin", "manager"):
        role_token = seed_member(
            db_session, company_id=company_id, email=f"rbac-brief-{role}@example.com", role=role
        )
        response = regenerate_brief(client, role_token)
        assert response.status_code == 201, (role, response.text)


# member is excluded from triggering regeneration
def test_member_cannot_regenerate(
    client: TestClient, fake_llm_provider: FakeLLMProvider, db_session: Session
) -> None:
    _owner_token, company_id = _seed_company_with_document(client, "rbac-brief-member-owner@example.com")
    member_token = seed_member(
        db_session, company_id=company_id, email="rbac-brief-member@example.com", role="member"
    )

    response = regenerate_brief(client, member_token)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


# all four roles can view an already-generated brief
def test_all_four_roles_can_view_brief(
    client: TestClient, fake_llm_provider: FakeLLMProvider, db_session: Session
) -> None:
    owner_token, company_id = _seed_company_with_document(client, "rbac-brief-view-owner@example.com")
    regenerate_response = regenerate_brief(client, owner_token)
    assert regenerate_response.status_code == 201

    for role in ("owner", "admin", "manager", "member"):
        role_token = (
            owner_token
            if role == "owner"
            else seed_member(
                db_session, company_id=company_id, email=f"rbac-brief-view-{role}@example.com", role=role
            )
        )
        response = get_brief(client, role_token)
        assert response.status_code == 200, (role, response.text)

        list_response = list_briefs(client, role_token)
        assert list_response.status_code == 200, role

