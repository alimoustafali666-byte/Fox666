import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage.factory import get_storage_provider
from app.db.session import set_company_context
from app.modules.audit_log.models import AuditLog
from app.modules.documents.models import Document
from tests.documents.helpers import PDF_BYTES, auth_header, create_project, signup, upload_file


def test_full_document_lifecycle_happy_path_and_cross_company_isolation(
    client: TestClient, db_session: Session
) -> None:
    # signup company -> authenticate
    token, claims = signup(client, "integration-owner@example.com", "Integration Co")
    company_id = uuid.UUID(claims["company_id"])

    # -> create project
    project = create_project(client, token, name="Integration Project")

    # -> upload a valid test PDF to project
    upload_response = upload_file(
        client, token, filename="contract.pdf", content=PDF_BYTES,
        project_id=project["id"], document_type="contract",
    )
    assert upload_response.status_code == 201, upload_response.text
    document = upload_response.json()
    document_id = document["id"]

    # -> document metadata exists
    get_response = client.get(f"/v1/documents/{document_id}", headers=auth_header(token))
    assert get_response.status_code == 200
    assert get_response.json()["file_name"] == "contract.pdf"
    assert get_response.json()["project_id"] == project["id"]

    # -> storage object exists
    set_company_context(db_session, company_id)
    row = db_session.execute(select(Document).where(Document.id == uuid.UUID(document_id))).scalar_one()
    provider = get_storage_provider()
    assert provider.exists(key=row.storage_key) is True

    # -> list documents returns it
    list_response = client.get("/v1/documents", headers=auth_header(token))
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()["items"]] == [document_id]

    # -> get metadata returns it (already proven above; re-verify post-list)
    assert client.get(f"/v1/documents/{document_id}", headers=auth_header(token)).status_code == 200

    # -> request download authorization -> signed URL generated
    download_response = client.get(
        f"/v1/documents/{document_id}/download", headers=auth_header(token)
    )
    assert download_response.status_code == 200
    assert download_response.json()["download_url"]

    # -> audit records exist
    set_company_context(db_session, company_id)
    actions = list(
        db_session.execute(select(AuditLog.action).order_by(AuditLog.created_at.asc())).scalars()
    )
    assert "document.upload" in actions
    assert "document.download" in actions

    # -> soft-delete document
    delete_response = client.delete(f"/v1/documents/{document_id}", headers=auth_header(token))
    assert delete_response.status_code == 200

    # -> document disappears from normal list/get
    assert client.get("/v1/documents", headers=auth_header(token)).json()["items"] == []
    assert client.get(f"/v1/documents/{document_id}", headers=auth_header(token)).status_code == 404

    # -> underlying storage object still exists
    assert provider.exists(key=row.storage_key) is True

    set_company_context(db_session, company_id)
    assert "document.delete" in list(
        db_session.execute(select(AuditLog.action)).scalars()
    )

    # --- a second company's user cannot access any part of this document ---
    other_token, _ = signup(client, "integration-outsider@example.com", "Other Co")

    assert client.get(f"/v1/documents/{document_id}", headers=auth_header(other_token)).status_code == 404
    assert (
        client.get(f"/v1/documents/{document_id}/download", headers=auth_header(other_token)).status_code
        == 404
    )
    assert client.delete(f"/v1/documents/{document_id}", headers=auth_header(other_token)).status_code == 404
    assert client.get("/v1/documents", headers=auth_header(other_token)).json()["items"] == []
    # cannot even associate a new upload with the first company's project
    other_upload = upload_file(
        client, other_token, filename="sneaky.pdf", content=PDF_BYTES, project_id=project["id"]
    )
    assert other_upload.status_code == 404

