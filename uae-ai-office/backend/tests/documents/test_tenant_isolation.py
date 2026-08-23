from fastapi.testclient import TestClient

from tests.documents.helpers import PDF_BYTES, auth_header, signup, upload_file


# 34. cross-company document cannot be read
def test_cross_company_document_cannot_be_read(client: TestClient) -> None:
    token_a, _ = signup(client, "iso-read-a@example.com", "Company A")
    token_b, _ = signup(client, "iso-read-b@example.com", "Company B")
    document = upload_file(client, token_b, filename="doc.pdf", content=PDF_BYTES).json()

    response = client.get(f"/v1/documents/{document['id']}", headers=auth_header(token_a))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


def test_cross_company_document_does_not_appear_in_list(client: TestClient) -> None:
    token_a, _ = signup(client, "iso-list-a@example.com", "Company A")
    token_b, _ = signup(client, "iso-list-b@example.com", "Company B")
    upload_file(client, token_b, filename="b-doc.pdf", content=PDF_BYTES)

    response = client.get("/v1/documents", headers=auth_header(token_a))

    assert response.status_code == 200
    assert response.json()["items"] == []


# 35. cross-company document cannot be downloaded
def test_cross_company_document_cannot_be_downloaded(client: TestClient) -> None:
    token_a, _ = signup(client, "iso-download-a@example.com", "Company A")
    token_b, _ = signup(client, "iso-download-b@example.com", "Company B")
    document = upload_file(client, token_b, filename="doc.pdf", content=PDF_BYTES).json()

    response = client.get(f"/v1/documents/{document['id']}/download", headers=auth_header(token_a))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


# 36. cross-company document cannot be deleted
def test_cross_company_document_cannot_be_deleted(client: TestClient) -> None:
    token_a, _ = signup(client, "iso-delete-a@example.com", "Company A")
    token_b, _ = signup(client, "iso-delete-b@example.com", "Company B")
    document = upload_file(client, token_b, filename="doc.pdf", content=PDF_BYTES).json()

    response = client.delete(f"/v1/documents/{document['id']}", headers=auth_header(token_a))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"

