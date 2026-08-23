import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage.keys import build_document_object_key
from app.db.session import set_company_context
from app.modules.documents.models import Document
from tests.documents.helpers import PDF_BYTES, auth_header, seed_member, signup, upload_file


# 1. owner can upload
def test_owner_can_upload(client: TestClient) -> None:
    token, _ = signup(client, "upload-owner@example.com")

    response = upload_file(client, token, filename="invoice.pdf", content=PDF_BYTES)

    assert response.status_code == 201, response.text


# 2. admin can upload
def test_admin_can_upload(client: TestClient, db_session: Session) -> None:
    _, owner_claims = signup(client, "upload-admin-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    admin_token = seed_member(db_session, company_id=company_id, email="upload-admin@example.com", role="admin")

    response = upload_file(client, admin_token, filename="invoice.pdf", content=PDF_BYTES)

    assert response.status_code == 201, response.text


# 3. manager can upload
def test_manager_can_upload(client: TestClient, db_session: Session) -> None:
    _, owner_claims = signup(client, "upload-manager-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    manager_token = seed_member(
        db_session, company_id=company_id, email="upload-manager@example.com", role="manager"
    )

    response = upload_file(client, manager_token, filename="invoice.pdf", content=PDF_BYTES)

    assert response.status_code == 201, response.text


# 4. member cannot upload
def test_member_cannot_upload(client: TestClient, db_session: Session) -> None:
    _, owner_claims = signup(client, "upload-member-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    member_token = seed_member(
        db_session, company_id=company_id, email="upload-member@example.com", role="member"
    )

    response = upload_file(client, member_token, filename="invoice.pdf", content=PDF_BYTES)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


# 5. company_id cannot be injected
def test_company_id_cannot_be_injected(client: TestClient) -> None:
    token, claims = signup(client, "upload-inject-company@example.com")
    forged_company_id = str(uuid.uuid4())

    response = client.post(
        "/v1/documents",
        headers=auth_header(token),
        data={"document_type": "contract", "company_id": forged_company_id},
        files={"file": ("invoice.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 201, response.text
    assert response.json()["company_id"] == claims["company_id"]
    assert response.json()["company_id"] != forged_company_id


# 6. uploaded_by is server-resolved
def test_uploaded_by_is_server_resolved(client: TestClient) -> None:
    token, claims = signup(client, "upload-resolved-by@example.com")
    forged_uploader = str(uuid.uuid4())

    response = client.post(
        "/v1/documents",
        headers=auth_header(token),
        data={"document_type": "contract", "uploaded_by": forged_uploader},
        files={"file": ("invoice.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 201, response.text
    assert response.json()["uploaded_by"] == claims["sub"]
    assert response.json()["uploaded_by"] != forged_uploader


# 7. storage_key is server-generated
def test_storage_key_is_server_generated(client: TestClient, db_session: Session) -> None:
    """storage_key is never accepted from the client (there's no field
    for it in the schema at all, and multipart form data is limited to
    file/project_id/document_type) -- this proves the value the server
    actually wrote matches the deterministic, company/document-namespaced
    format build_document_object_key produces, regardless of anything
    the client sent.
    """
    token, claims = signup(client, "upload-storage-key@example.com")
    forged_key = "companies/not-my-company/documents/whatever/original"

    response = client.post(
        "/v1/documents",
        headers=auth_header(token),
        data={"document_type": "contract", "storage_key": forged_key},
        files={"file": ("invoice.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 201, response.text
    document_id = response.json()["id"]

    company_id = uuid.UUID(claims["company_id"])
    set_company_context(db_session, company_id)
    row = db_session.execute(
        select(Document).where(Document.id == uuid.UUID(document_id))
    ).scalar_one()

    expected_key = build_document_object_key(company_id=company_id, document_id=row.id)
    assert row.storage_key == expected_key
    assert row.storage_key != forged_key

