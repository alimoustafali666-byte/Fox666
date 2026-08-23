import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.embeddings.exceptions import EmbeddingUnavailable
from app.core.embeddings.factory import get_embedding_provider
from app.db.session import set_company_context
from app.modules.audit_log.models import AuditLog
from tests.documents.helpers import auth_header, signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes, upload_and_get_document

_PDF_BYTES = build_native_text_pdf_bytes(
    ["A distinctive marker: ZEBRA-EMBED-MARKER-8823, real extractable content."]
)


def _entries_for(db_session: Session, company_id: uuid.UUID) -> list[AuditLog]:
    set_company_context(db_session, company_id)
    return list(db_session.execute(select(AuditLog).order_by(AuditLog.created_at.asc())).scalars())


# 40. indexing audits are written
def test_indexing_success_is_audited(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "audit-index-success@example.com")
    doc = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)
    client.post(f"/v1/documents/{doc['id']}/process", headers=auth_header(token))

    client.post(f"/v1/documents/{doc['id']}/index", headers=auth_header(token))

    actions = [e.action for e in _entries_for(db_session, uuid.UUID(claims["company_id"]))]
    assert "document.indexing_started" in actions
    assert "document.indexing_succeeded" in actions


def test_indexing_failure_is_audited(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, claims = signup(client, "audit-index-failure@example.com")
    doc = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)
    client.post(f"/v1/documents/{doc['id']}/process", headers=auth_header(token))

    provider = get_embedding_provider()

    def boom(texts):
        raise EmbeddingUnavailable("down")

    monkeypatch.setattr(provider, "embed_batch", boom)

    client.post(f"/v1/documents/{doc['id']}/index", headers=auth_header(token))

    entries = _entries_for(db_session, uuid.UUID(claims["company_id"]))
    actions = [e.action for e in entries]
    assert "document.indexing_failed" in actions
    failure_entry = next(e for e in entries if e.action == "document.indexing_failed")
    assert failure_entry.metadata_["failure_category"] == "embedding_provider_unavailable"


# 41. embeddings/chunk content not written to audit metadata
def test_chunk_content_never_appears_in_indexing_audit_metadata(
    client: TestClient, db_session: Session
) -> None:
    token, claims = signup(client, "audit-index-no-content@example.com")
    doc = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)
    client.post(f"/v1/documents/{doc['id']}/process", headers=auth_header(token))

    client.post(f"/v1/documents/{doc['id']}/index", headers=auth_header(token))

    entries = _entries_for(db_session, uuid.UUID(claims["company_id"]))
    metadata_text = str([e.metadata_ for e in entries])
    assert "ZEBRA-EMBED-MARKER-8823" not in metadata_text


def test_embedding_vector_never_appears_in_indexing_audit_metadata(
    client: TestClient, db_session: Session
) -> None:
    token, claims = signup(client, "audit-index-no-vector@example.com")
    doc = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)
    client.post(f"/v1/documents/{doc['id']}/process", headers=auth_header(token))

    client.post(f"/v1/documents/{doc['id']}/index", headers=auth_header(token))

    entries = _entries_for(db_session, uuid.UUID(claims["company_id"]))
    for entry in entries:
        if entry.metadata_ is None:
            continue
        # no metadata value is ever a long list of numbers (a vector) --
        # every field is a scalar/short string/small nested dict.
        for value in entry.metadata_.values():
            assert not (isinstance(value, list) and len(value) > 10)


def test_audit_metadata_contains_no_sensitive_material(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "audit-index-safe-metadata@example.com")
    doc = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)
    client.post(f"/v1/documents/{doc['id']}/process", headers=auth_header(token))
    client.post(f"/v1/documents/{doc['id']}/index", headers=auth_header(token))

    metadata_text = str(
        [e.metadata_ for e in _entries_for(db_session, uuid.UUID(claims["company_id"]))]
    ).lower()
    for forbidden in ("authorization", "cookie", "password", "token", "api_key", "apikey"):
        assert forbidden not in metadata_text

