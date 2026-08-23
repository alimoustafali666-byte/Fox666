import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.documents.helpers import (
    PDF_BYTES,
    auth_header,
    create_project,
    seed_member,
    signup,
    upload_file,
)


# 28. owner can list documents
def test_owner_can_list_documents(client: TestClient) -> None:
    token, _ = signup(client, "list-owner@example.com")
    upload_file(client, token, filename="doc.pdf", content=PDF_BYTES)

    response = client.get("/v1/documents", headers=auth_header(token))

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


# 29. member can list/read documents
def test_member_can_list_and_read_documents(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "list-member-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    uploaded = upload_file(client, owner_token, filename="doc.pdf", content=PDF_BYTES).json()
    member_token = seed_member(
        db_session, company_id=company_id, email="list-member@example.com", role="member"
    )

    list_response = client.get("/v1/documents", headers=auth_header(member_token))
    get_response = client.get(f"/v1/documents/{uploaded['id']}", headers=auth_header(member_token))

    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1
    assert get_response.status_code == 200


# 30. project_id filter works
def test_project_id_filter_works(client: TestClient) -> None:
    token, _ = signup(client, "list-filter-project@example.com")
    project = create_project(client, token)
    upload_file(client, token, filename="in-project.pdf", content=PDF_BYTES, project_id=project["id"])
    upload_file(client, token, filename="company-level.pdf", content=PDF_BYTES)

    response = client.get(f"/v1/documents?project_id={project['id']}", headers=auth_header(token))

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["file_name"] == "in-project.pdf"


# 31. document_type filter works
def test_document_type_filter_works(client: TestClient) -> None:
    token, _ = signup(client, "list-filter-doctype@example.com")
    upload_file(client, token, filename="a.pdf", content=PDF_BYTES, document_type="invoice")
    upload_file(client, token, filename="b.pdf", content=PDF_BYTES, document_type="contract")

    response = client.get("/v1/documents?document_type=invoice", headers=auth_header(token))

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["document_type"] == "invoice"


def test_unknown_document_type_filter_is_rejected_cleanly(client: TestClient) -> None:
    token, _ = signup(client, "list-filter-doctype-bad@example.com")

    response = client.get("/v1/documents?document_type=not_a_real_type", headers=auth_header(token))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


# 32. pagination is bounded
def test_pagination_is_bounded(client: TestClient) -> None:
    token, _ = signup(client, "list-paginate@example.com")
    for i in range(15):
        upload_file(client, token, filename=f"doc-{i}.pdf", content=PDF_BYTES)

    response = client.get("/v1/documents?limit=10", headers=auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 10
    assert body["next_cursor"] is not None

    second_page = client.get(
        f"/v1/documents?limit=10&cursor={body['next_cursor']}", headers=auth_header(token)
    )
    assert len(second_page.json()["items"]) == 5
    assert second_page.json()["next_cursor"] is None


def test_pagination_limit_is_capped(client: TestClient) -> None:
    token, _ = signup(client, "list-paginate-cap@example.com")

    response = client.get("/v1/documents?limit=99999", headers=auth_header(token))

    assert response.status_code == 422


# 33. soft-deleted documents excluded from list
def test_soft_deleted_documents_excluded_from_list(client: TestClient) -> None:
    token, _ = signup(client, "list-excludes-deleted@example.com")
    uploaded = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES).json()

    client.delete(f"/v1/documents/{uploaded['id']}", headers=auth_header(token))
    response = client.get("/v1/documents", headers=auth_header(token))

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_get_soft_deleted_document_behaves_as_not_found(client: TestClient) -> None:
    token, _ = signup(client, "get-excludes-deleted@example.com")
    uploaded = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES).json()

    client.delete(f"/v1/documents/{uploaded['id']}", headers=auth_header(token))
    response = client.get(f"/v1/documents/{uploaded['id']}", headers=auth_header(token))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


def test_get_nonexistent_document_returns_404(client: TestClient) -> None:
    token, _ = signup(client, "get-nonexistent@example.com")

    response = client.get(f"/v1/documents/{uuid.uuid4()}", headers=auth_header(token))

    assert response.status_code == 404

