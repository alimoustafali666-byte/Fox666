import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.documents.helpers import auth_header, seed_member, signup
from tests.documents.processing.helpers import (
    build_native_text_pdf_bytes,
    trigger_processing,
    upload_and_get_document,
)

_PDF_BYTES = build_native_text_pdf_bytes(["Some real extractable text content."])


# 25. owner can process
def test_owner_can_process(client: TestClient) -> None:
    token, _ = signup(client, "proc-rbac-owner@example.com")
    document = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)

    response = trigger_processing(client, token, document["id"])

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "processed"


# 26. admin can process
def test_admin_can_process(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "proc-rbac-admin-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    document = upload_and_get_document(client, owner_token, filename="doc.pdf", content=_PDF_BYTES)
    admin_token = seed_member(db_session, company_id=company_id, email="proc-rbac-admin@example.com", role="admin")

    response = trigger_processing(client, admin_token, document["id"])

    assert response.status_code == 200, response.text


# 27. manager can process
def test_manager_can_process(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "proc-rbac-manager-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    document = upload_and_get_document(client, owner_token, filename="doc.pdf", content=_PDF_BYTES)
    manager_token = seed_member(
        db_session, company_id=company_id, email="proc-rbac-manager@example.com", role="manager"
    )

    response = trigger_processing(client, manager_token, document["id"])

    assert response.status_code == 200, response.text


# 28. member cannot process
def test_member_cannot_process(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "proc-rbac-member-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    document = upload_and_get_document(client, owner_token, filename="doc.pdf", content=_PDF_BYTES)
    member_token = seed_member(
        db_session, company_id=company_id, email="proc-rbac-member@example.com", role="member"
    )

    response = trigger_processing(client, member_token, document["id"])

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


# 29. cross-company document cannot be processed
def test_cross_company_document_cannot_be_processed(client: TestClient) -> None:
    token_a, _ = signup(client, "proc-iso-a@example.com", "Company A")
    token_b, _ = signup(client, "proc-iso-b@example.com", "Company B")
    document = upload_and_get_document(client, token_b, filename="doc.pdf", content=_PDF_BYTES)

    response = trigger_processing(client, token_a, document["id"])

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


# 30. deleted document cannot be processed
def test_deleted_document_cannot_be_processed(client: TestClient) -> None:
    token, _ = signup(client, "proc-deleted@example.com")
    document = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)
    client.delete(f"/v1/documents/{document['id']}", headers=auth_header(token))

    response = trigger_processing(client, token, document["id"])

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


def test_processing_nonexistent_document_returns_404(client: TestClient) -> None:
    token, _ = signup(client, "proc-nonexistent@example.com")

    response = trigger_processing(client, token, uuid.uuid4())

    assert response.status_code == 404

