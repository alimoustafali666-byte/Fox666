import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import set_company_context
from app.modules.audit_log.models import AuditLog
from tests.documents.helpers import PDF_BYTES, auth_header, signup, upload_file


def _entries_for(db_session: Session, company_id: uuid.UUID) -> list[AuditLog]:
    set_company_context(db_session, company_id)
    return list(
        db_session.execute(select(AuditLog).order_by(AuditLog.created_at.asc())).scalars()
    )


# 47. document.upload audit written
def test_document_upload_writes_audit_event(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "audit-upload@example.com")
    company_id = uuid.UUID(claims["company_id"])

    upload_file(client, token, filename="doc.pdf", content=PDF_BYTES)

    actions = [e.action for e in _entries_for(db_session, company_id)]
    assert "document.upload" in actions


# 48. document.download audit written
def test_document_download_writes_audit_event(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "audit-download@example.com")
    company_id = uuid.UUID(claims["company_id"])
    document = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES).json()

    client.get(f"/v1/documents/{document['id']}/download", headers=auth_header(token))

    actions = [e.action for e in _entries_for(db_session, company_id)]
    assert "document.download" in actions


# 49. document.delete audit event is written
def test_document_delete_writes_audit_event(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "audit-delete@example.com")
    company_id = uuid.UUID(claims["company_id"])
    document = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES).json()

    client.delete(f"/v1/documents/{document['id']}", headers=auth_header(token))

    actions = [e.action for e in _entries_for(db_session, company_id)]
    assert "document.delete" in actions


# 50. signed URL is not stored in audit metadata
def test_signed_url_not_stored_in_audit_metadata(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "audit-no-url@example.com")
    company_id = uuid.UUID(claims["company_id"])
    document = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES).json()

    download_response = client.get(
        f"/v1/documents/{document['id']}/download", headers=auth_header(token)
    )
    signed_url = download_response.json()["download_url"]

    entry = next(e for e in _entries_for(db_session, company_id) if e.action == "document.download")
    assert signed_url not in str(entry.metadata_)


# 51. raw file content is never written to audit metadata
def test_raw_file_content_not_stored_in_audit_metadata(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "audit-no-content@example.com")
    company_id = uuid.UUID(claims["company_id"])
    distinctive_marker = b"UNIQUE-FILE-BODY-MARKER-98765"

    upload_file(client, token, filename="doc.pdf", content=PDF_BYTES + distinctive_marker)

    entry = next(e for e in _entries_for(db_session, company_id) if e.action == "document.upload")
    assert distinctive_marker.decode() not in str(entry.metadata_)
    # nor the internal storage key, which is a documented internal
    # implementation detail this metadata has no need to carry
    assert "companies/" not in str(entry.metadata_)


def test_audit_metadata_contains_no_sensitive_material(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "audit-safe-metadata@example.com")
    company_id = uuid.UUID(claims["company_id"])
    upload_file(client, token, filename="doc.pdf", content=PDF_BYTES)

    metadata_text = str([e.metadata_ for e in _entries_for(db_session, company_id)]).lower()
    for forbidden in ("authorization", "cookie", "password", "token"):
        assert forbidden not in metadata_text

