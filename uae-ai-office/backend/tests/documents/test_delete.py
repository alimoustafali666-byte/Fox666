import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage.factory import get_storage_provider
from app.db.session import set_company_context
from app.modules.documents.models import Document
from tests.documents.helpers import PDF_BYTES, auth_header, seed_member, signup, upload_file


# 37. owner can delete
def test_owner_can_delete(client: TestClient) -> None:
    token, _ = signup(client, "delete-owner@example.com")
    uploaded = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES).json()

    response = client.delete(f"/v1/documents/{uploaded['id']}", headers=auth_header(token))

    assert response.status_code == 200


# 38. admin can delete
def test_admin_can_delete(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "delete-admin-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    uploaded = upload_file(client, owner_token, filename="doc.pdf", content=PDF_BYTES).json()
    admin_token = seed_member(db_session, company_id=company_id, email="delete-admin@example.com", role="admin")

    response = client.delete(f"/v1/documents/{uploaded['id']}", headers=auth_header(admin_token))

    assert response.status_code == 200


# 39. manager cannot delete
def test_manager_cannot_delete(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "delete-manager-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    uploaded = upload_file(client, owner_token, filename="doc.pdf", content=PDF_BYTES).json()
    manager_token = seed_member(
        db_session, company_id=company_id, email="delete-manager@example.com", role="manager"
    )

    response = client.delete(f"/v1/documents/{uploaded['id']}", headers=auth_header(manager_token))

    assert response.status_code == 403


# 40. member cannot delete
def test_member_cannot_delete(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "delete-member-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    uploaded = upload_file(client, owner_token, filename="doc.pdf", content=PDF_BYTES).json()
    member_token = seed_member(
        db_session, company_id=company_id, email="delete-member@example.com", role="member"
    )

    response = client.delete(f"/v1/documents/{uploaded['id']}", headers=auth_header(member_token))

    assert response.status_code == 403


# 41. DELETE soft-deletes DB row
def test_delete_soft_deletes_the_row(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "delete-soft@example.com")
    uploaded = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES).json()

    client.delete(f"/v1/documents/{uploaded['id']}", headers=auth_header(token))

    set_company_context(db_session, uuid.UUID(claims["company_id"]))
    row = db_session.execute(
        select(Document).where(Document.id == uuid.UUID(uploaded["id"]))
    ).scalar_one()

    assert row is not None
    assert row.deleted_at is not None


# 42. DELETE does not remove storage object
def test_delete_does_not_remove_storage_object(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "delete-keeps-storage@example.com")
    uploaded = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES).json()

    client.delete(f"/v1/documents/{uploaded['id']}", headers=auth_header(token))

    set_company_context(db_session, uuid.UUID(claims["company_id"]))
    row = db_session.execute(
        select(Document).where(Document.id == uuid.UUID(uploaded["id"]))
    ).scalar_one()

    provider = get_storage_provider()
    assert provider.exists(key=row.storage_key) is True


# 43. soft-deleted document cannot be normally downloaded
def test_soft_deleted_document_cannot_be_downloaded(client: TestClient) -> None:
    token, _ = signup(client, "delete-no-download@example.com")
    uploaded = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES).json()

    client.delete(f"/v1/documents/{uploaded['id']}", headers=auth_header(token))
    response = client.get(f"/v1/documents/{uploaded['id']}/download", headers=auth_header(token))

    assert response.status_code == 404


def test_deleting_an_already_deleted_document_is_a_consistent_safe_result(client: TestClient) -> None:
    token, _ = signup(client, "delete-twice@example.com")
    uploaded = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES).json()

    first = client.delete(f"/v1/documents/{uploaded['id']}", headers=auth_header(token))
    second = client.delete(f"/v1/documents/{uploaded['id']}", headers=auth_header(token))

    assert first.status_code == 200
    # Documents are hidden from every normal endpoint once soft-deleted --
    # re-deleting is therefore the same safe 404 as any other not-found
    # document, consistent with GET/list/download behavior above.
    assert second.status_code == 404

