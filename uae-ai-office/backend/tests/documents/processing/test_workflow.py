import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage.exceptions import StorageUnavailable
from app.core.storage.factory import get_storage_provider
from app.db.session import set_company_context
from app.modules.audit_log.models import AuditLog
from app.modules.documents.models import Document, DocumentChunk
from tests.documents.helpers import signup
from tests.documents.processing.helpers import (
    build_empty_pdf_bytes,
    build_native_text_pdf_bytes,
    trigger_processing,
    upload_and_get_document,
)

_PDF_BYTES = build_native_text_pdf_bytes(["Real extractable content for workflow tests."])


def _chunks_for(db_session: Session, *, company_id: uuid.UUID, document_id: uuid.UUID) -> list[DocumentChunk]:
    set_company_context(db_session, company_id)
    return list(
        db_session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        ).scalars()
    )


# 31. uploaded -> processing -> processed works
def test_uploaded_to_processing_to_processed(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "workflow-happy@example.com")
    document = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)
    assert document["status"] == "uploaded"

    response = trigger_processing(client, token, document["id"])

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "processed"
    chunks = _chunks_for(
        db_session, company_id=uuid.UUID(claims["company_id"]), document_id=uuid.UUID(document["id"])
    )
    assert len(chunks) > 0


# 32. processing failure results in failed status
def test_processing_failure_results_in_failed_status(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "workflow-failure@example.com")
    document = upload_and_get_document(
        client, token, filename="scanned.pdf", content=build_empty_pdf_bytes()
    )

    response = trigger_processing(client, token, document["id"])

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "insufficient_text"

    set_company_context(db_session, uuid.UUID(claims["company_id"]))
    row = db_session.execute(
        select(Document).where(Document.id == uuid.UUID(document["id"]))
    ).scalar_one()
    assert row.status == "failed"
    assert row.processing_error_code == "insufficient_text"
    assert row.processing_error_message is not None


# 33. failed document can be retried
def test_failed_document_can_be_retried_and_succeed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, _ = signup(client, "workflow-retry@example.com")
    document = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)

    provider = get_storage_provider()
    real_download = provider.download
    call_count = {"n": 0}

    def flaky_download(*, key: str):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise StorageUnavailable("simulated transient storage failure")
        return real_download(key=key)

    monkeypatch.setattr(provider, "download", flaky_download)

    first = trigger_processing(client, token, document["id"])
    assert first.status_code == 503
    assert first.json()["error"]["code"] == "processing_unavailable"

    second = trigger_processing(client, token, document["id"])
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "processed"


# 34. processed document can be safely reprocessed
def test_processed_document_can_be_safely_reprocessed(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "workflow-reprocess@example.com")
    document = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)
    trigger_processing(client, token, document["id"])

    response = trigger_processing(client, token, document["id"])

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "processed"

    set_company_context(db_session, uuid.UUID(claims["company_id"]))
    actions = list(
        db_session.execute(select(AuditLog.action).order_by(AuditLog.created_at.asc())).scalars()
    )
    assert actions.count("document.processing_succeeded") == 2
    assert "document.reprocessed" in actions


# 35. successful reprocessing does not duplicate chunks
def test_successful_reprocessing_does_not_duplicate_chunks(
    client: TestClient, db_session: Session
) -> None:
    token, claims = signup(client, "workflow-no-dup@example.com")
    document = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)
    company_id = uuid.UUID(claims["company_id"])
    document_id = uuid.UUID(document["id"])

    trigger_processing(client, token, document["id"])
    first_count = len(_chunks_for(db_session, company_id=company_id, document_id=document_id))

    trigger_processing(client, token, document["id"])
    second_count = len(_chunks_for(db_session, company_id=company_id, document_id=document_id))

    assert first_count > 0
    assert second_count == first_count


# 36. failed reprocessing does not destroy previous known-good chunks
def test_failed_reprocessing_preserves_previous_known_good_chunks(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, claims = signup(client, "workflow-preserve-good@example.com")
    document = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)
    company_id = uuid.UUID(claims["company_id"])
    document_id = uuid.UUID(document["id"])

    first = trigger_processing(client, token, document["id"])
    assert first.status_code == 200
    good_chunks = _chunks_for(db_session, company_id=company_id, document_id=document_id)
    assert len(good_chunks) > 0
    good_contents = [c.content for c in good_chunks]

    provider = get_storage_provider()

    def always_fails(*, key: str):
        raise StorageUnavailable("simulated permanent storage failure")

    monkeypatch.setattr(provider, "download", always_fails)

    second = trigger_processing(client, token, document["id"])
    assert second.status_code == 503

    still_there = _chunks_for(db_session, company_id=company_id, document_id=document_id)
    assert [c.content for c in still_there] == good_contents

    set_company_context(db_session, company_id)
    row = db_session.execute(select(Document).where(Document.id == document_id)).scalar_one()
    assert row.status == "failed"


def test_processing_endpoint_returns_bounded_ttl_no_raw_exception_text(client: TestClient) -> None:
    """Sanity check that a failure response never contains raw
    exception/library text -- see the dedicated leakage tests too.
    """
    token, _ = signup(client, "workflow-safe-error@example.com")
    document = upload_and_get_document(
        client, token, filename="scanned.pdf", content=build_empty_pdf_bytes()
    )

    response = trigger_processing(client, token, document["id"])

    body_text = response.text.lower()
    for forbidden in ("traceback", "pdfminer", "pdfplumber", "site-packages"):
        assert forbidden not in body_text

