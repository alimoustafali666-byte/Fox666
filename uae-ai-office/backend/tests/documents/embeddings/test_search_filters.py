from fastapi.testclient import TestClient

from tests.documents.embeddings.helpers import search, upload_process_and_index
from tests.documents.helpers import auth_header, create_project, signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes

_CONTRACT_PDF = build_native_text_pdf_bytes(["Contract terms about steel beam delivery schedule."])
_INVOICE_PDF = build_native_text_pdf_bytes(["Invoice amount for steel beam delivery schedule."])


# 26. document_id filter works
def test_document_id_filter_scopes_to_one_document(client: TestClient) -> None:
    token, _ = signup(client, "search-filter-doc-id@example.com")
    doc_a = upload_process_and_index(client, token, filename="a.pdf", content=_CONTRACT_PDF)
    upload_process_and_index(client, token, filename="b.pdf", content=_INVOICE_PDF)

    response = search(client, token, query="steel beam delivery schedule", document_id=doc_a["id"])

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    assert all(item["document_id"] == doc_a["id"] for item in items)


# 27. project_id filter works
def test_project_id_filter_scopes_to_one_project(client: TestClient) -> None:
    token, _ = signup(client, "search-filter-project-id@example.com")
    project = create_project(client, token, name="Steel Project")
    upload_process_and_index(
        client, token, filename="in-project.pdf", content=_CONTRACT_PDF, project_id=project["id"]
    )
    upload_process_and_index(client, token, filename="company-level.pdf", content=_INVOICE_PDF)

    response = search(client, token, query="steel beam delivery schedule", project_id=project["id"])

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    for item in items:
        get_response = client.get(f"/v1/documents/{item['document_id']}", headers=auth_header(token))
        assert get_response.json()["project_id"] == project["id"]


# 28. document_type filter works
def test_document_type_filter_scopes_results(client: TestClient) -> None:
    token, _ = signup(client, "search-filter-doctype@example.com")
    upload_process_and_index(
        client, token, filename="contract.pdf", content=_CONTRACT_PDF, document_type="contract"
    )
    upload_process_and_index(
        client, token, filename="invoice.pdf", content=_INVOICE_PDF, document_type="invoice"
    )

    response = search(client, token, query="steel beam delivery schedule", document_type="invoice")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    for item in items:
        get_response = client.get(f"/v1/documents/{item['document_id']}", headers=auth_header(token))
        assert get_response.json()["document_type"] == "invoice"


def test_unknown_document_type_filter_is_rejected_cleanly(client: TestClient) -> None:
    token, _ = signup(client, "search-filter-doctype-bad@example.com")

    response = search(client, token, query="anything", document_type="not_a_real_type")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


def test_filters_can_combine(client: TestClient) -> None:
    token, _ = signup(client, "search-filter-combine@example.com")
    project = create_project(client, token, name="Combined Project")
    doc = upload_process_and_index(
        client, token, filename="a.pdf", content=_CONTRACT_PDF,
        project_id=project["id"], document_type="contract",
    )

    response = search(
        client, token, query="steel beam delivery schedule",
        project_id=project["id"], document_type="contract",
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    assert all(item["document_id"] == doc["id"] for item in items)

