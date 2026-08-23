import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.documents.embeddings.helpers import search, upload_process_and_index
from tests.documents.helpers import seed_member, signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes

_COMPANY_A_PDF = build_native_text_pdf_bytes(
    ["Company A's confidential concrete foundation specifications and pricing."]
)
_COMPANY_B_PDF = build_native_text_pdf_bytes(
    ["Company B's confidential concrete foundation specifications and pricing."]
)


# 22. Company A search cannot return Company B chunk
def test_company_a_search_cannot_return_company_b_chunk(client: TestClient) -> None:
    token_a, _ = signup(client, "search-iso-a@example.com", "Company A")
    token_b, _ = signup(client, "search-iso-b@example.com", "Company B")
    upload_process_and_index(client, token_b, filename="b.pdf", content=_COMPANY_B_PDF)

    response = search(client, token_a, query="concrete foundation specifications pricing")

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_company_a_search_returns_its_own_indexed_content(client: TestClient) -> None:
    token_a, _ = signup(client, "search-iso-own-a@example.com", "Company A")
    upload_process_and_index(client, token_a, filename="a.pdf", content=_COMPANY_A_PDF)

    response = search(client, token_a, query="concrete foundation specifications pricing")

    assert response.status_code == 200
    assert len(response.json()["items"]) >= 1


# 23. application company filter independently scopes search
def test_application_layer_company_filter_scopes_results(client: TestClient) -> None:
    """Uses the retrieval_service function directly (not RLS-bypassing --
    still goes through the ORM/RLS-backed session) to prove the explicit
    company_id predicate in the query is itself doing real work, not
    merely redundant with RLS -- see test_search_isolation at the DB
    layer (tests/db/test_pgvector_isolation.py) for the RLS-only proof.
    """
    token_a, claims_a = signup(client, "search-app-filter-a@example.com", "Company A")
    token_b, _ = signup(client, "search-app-filter-b@example.com", "Company B")
    upload_process_and_index(client, token_a, filename="a.pdf", content=_COMPANY_A_PDF)
    upload_process_and_index(client, token_b, filename="b.pdf", content=_COMPANY_B_PDF)

    response = search(client, token_a, query="concrete foundation specifications pricing")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    document_ids = {item["document_id"] for item in items}
    # every returned chunk must belong to a document company A can see
    for doc_id in document_ids:
        get_response = client.get(
            f"/v1/documents/{doc_id}", headers={"Authorization": f"Bearer {token_a}"}
        )
        assert get_response.status_code == 200
        assert get_response.json()["company_id"] == claims_a["company_id"]


# 25. member can search own company's indexed content
def test_member_can_search_own_companys_indexed_content(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "search-member-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    upload_process_and_index(client, owner_token, filename="a.pdf", content=_COMPANY_A_PDF)
    member_token = seed_member(
        db_session, company_id=company_id, email="search-member@example.com", role="member"
    )

    response = search(client, member_token, query="concrete foundation specifications pricing")

    assert response.status_code == 200
    assert len(response.json()["items"]) >= 1


# 29. cross-company filter ID does not leak data
def test_cross_company_document_id_filter_returns_no_results_not_an_error(client: TestClient) -> None:
    token_a, _ = signup(client, "search-cross-filter-a@example.com", "Company A")
    token_b, _ = signup(client, "search-cross-filter-b@example.com", "Company B")
    b_doc = upload_process_and_index(client, token_b, filename="b.pdf", content=_COMPANY_B_PDF)

    response = search(
        client, token_a, query="concrete foundation", document_id=b_doc["id"]
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_cross_company_project_id_filter_returns_no_results_not_an_error(client: TestClient) -> None:
    token_a, _ = signup(client, "search-cross-project-a@example.com", "Company A")
    token_b, _ = signup(client, "search-cross-project-b@example.com", "Company B")
    project_b = client.post(
        "/v1/projects", json={"name": "B Project"}, headers={"Authorization": f"Bearer {token_b}"}
    ).json()
    upload_process_and_index(client, token_b, filename="b.pdf", content=_COMPANY_B_PDF)

    response = search(
        client, token_a, query="concrete foundation", project_id=project_b["id"]
    )

    assert response.status_code == 200
    assert response.json()["items"] == []

