from fastapi.testclient import TestClient

from tests.documents.helpers import PDF_BYTES, create_project, signup, upload_file


# 23. project_id may be null
def test_project_id_may_be_null(client: TestClient) -> None:
    token, _ = signup(client, "project-null@example.com")

    response = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES)

    assert response.status_code == 201, response.text
    assert response.json()["project_id"] is None


# 24. valid same-company project association works
def test_valid_same_company_project_association_works(client: TestClient) -> None:
    token, _ = signup(client, "project-same-company@example.com")
    project = create_project(client, token)

    response = upload_file(
        client, token, filename="doc.pdf", content=PDF_BYTES, project_id=project["id"]
    )

    assert response.status_code == 201, response.text
    assert response.json()["project_id"] == project["id"]


# 25. cross-company project association is rejected
def test_cross_company_project_association_is_rejected(client: TestClient) -> None:
    token_a, _ = signup(client, "project-cross-a@example.com", "Company A")
    token_b, _ = signup(client, "project-cross-b@example.com", "Company B")
    project_b = create_project(client, token_b, name="B's Project")

    response = upload_file(
        client, token_a, filename="doc.pdf", content=PDF_BYTES, project_id=project_b["id"]
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "project_not_found"


# 26. company-level document works
def test_company_level_document_works(client: TestClient) -> None:
    token, _ = signup(client, "project-company-level@example.com")

    response = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES)

    assert response.status_code == 201, response.text
    assert response.json()["project_id"] is None


def test_cancelled_project_can_still_receive_documents(client: TestClient) -> None:
    """Explicitly approved: a cancelled project may still hold/read
    documents -- no stricter behavior was requested.
    """
    token, _ = signup(client, "project-cancelled@example.com")
    project = create_project(client, token)
    client.delete(f"/v1/projects/{project['id']}", headers={"Authorization": f"Bearer {token}"})

    response = upload_file(
        client, token, filename="doc.pdf", content=PDF_BYTES, project_id=project["id"]
    )

    assert response.status_code == 201, response.text


# 27. document_type validation works
def test_document_type_validation_rejects_unknown_value(client: TestClient) -> None:
    token, _ = signup(client, "project-doctype-invalid@example.com")

    response = upload_file(
        client, token, filename="doc.pdf", content=PDF_BYTES, document_type="not_a_real_type"
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_document_type"


def test_document_type_validation_accepts_each_known_value(client: TestClient) -> None:
    token, _ = signup(client, "project-doctype-valid@example.com")

    for document_type in (
        "contract", "boq", "quotation", "invoice", "purchase_order", "project_report", "other",
    ):
        response = upload_file(
            client, token, filename="doc.pdf", content=PDF_BYTES, document_type=document_type
        )
        assert response.status_code == 201, response.text
        assert response.json()["document_type"] == document_type

