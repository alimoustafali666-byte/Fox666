import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage.exceptions import StorageUnavailable
from app.core.storage.factory import get_storage_provider
from app.db.session import set_company_context
from app.modules.audit_log.models import AuditLog
from app.modules.documents.models import Document
from tests.documents.helpers import signup
from tests.documents.processing.helpers import (
    build_empty_pdf_bytes,
    build_native_text_pdf_bytes,
    build_xlsx_bytes,
    trigger_processing,
    upload_and_get_document,
)

_PDF_BYTES = build_native_text_pdf_bytes(["A distinctive marker: ZEBRA-UNIQUE-CONTENT-4471."])


def _actions_for(db_session: Session, company_id: uuid.UUID) -> list[AuditLog]:
    set_company_context(db_session, company_id)
    return list(db_session.execute(select(AuditLog).order_by(AuditLog.created_at.asc())).scalars())


# 41. processing success audited
def test_processing_success_audited(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "audit-proc-success@example.com")
    document = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)

    trigger_processing(client, token, document["id"])

    entries = _actions_for(db_session, uuid.UUID(claims["company_id"]))
    actions = [e.action for e in entries]
    assert "document.processing_started" in actions
    assert "document.processing_succeeded" in actions


# 42. processing failure audited
def test_processing_failure_audited(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "audit-proc-failure@example.com")
    document = upload_and_get_document(
        client, token, filename="scanned.pdf", content=build_empty_pdf_bytes()
    )

    trigger_processing(client, token, document["id"])

    entries = _actions_for(db_session, uuid.UUID(claims["company_id"]))
    actions = [e.action for e in entries]
    assert "document.processing_started" in actions
    assert "document.processing_failed" in actions
    failure_entry = next(e for e in entries if e.action == "document.processing_failed")
    assert failure_entry.metadata_["failure_category"] == "insufficient_text"


# 40. extracted content is not written into audit metadata
def test_extracted_content_never_appears_in_audit_metadata(
    client: TestClient, db_session: Session
) -> None:
    token, claims = signup(client, "audit-proc-no-content@example.com")
    document = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)

    trigger_processing(client, token, document["id"])

    entries = _actions_for(db_session, uuid.UUID(claims["company_id"]))
    metadata_text = str([e.metadata_ for e in entries])
    assert "ZEBRA-UNIQUE-CONTENT-4471" not in metadata_text


def test_storage_key_never_appears_in_audit_metadata(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "audit-proc-no-key@example.com")
    document = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)
    trigger_processing(client, token, document["id"])

    set_company_context(db_session, uuid.UUID(claims["company_id"]))
    row = db_session.execute(
        select(Document).where(Document.id == uuid.UUID(document["id"]))
    ).scalar_one()

    entries = _actions_for(db_session, uuid.UUID(claims["company_id"]))
    metadata_text = str([e.metadata_ for e in entries])
    assert row.storage_key not in metadata_text


# 39. storage_key never exposed (API response)
def test_storage_key_never_appears_in_process_response(client: TestClient) -> None:
    token, _ = signup(client, "proc-no-leak-response@example.com")
    document = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)

    response = trigger_processing(client, token, document["id"])

    assert "storage_key" not in response.text


# 37. parser error does not leak stack trace
def test_parser_failure_response_never_leaks_internals(client: TestClient) -> None:
    token, _ = signup(client, "proc-no-leak-parser@example.com")
    # a .docx upload whose content is actually plain text will fail Step 8's
    # own upload validation, so instead force a parse failure through a
    # file that passes upload validation (real docx/xlsx/pdf) but is
    # pathologically malformed for pdfplumber to choke on: truncate a
    # real PDF's content stream.
    document = upload_and_get_document(
        client, token, filename="broken.pdf", content=b"%PDF-1.4\ngarbage, not a real body\n%%EOF"
    )

    response = trigger_processing(client, token, document["id"])

    body_text = response.text.lower()
    for forbidden in ("traceback", "site-packages", ".py", "pdfminer", "line "):
        assert forbidden not in body_text


# 38. storage failure handled safely
def test_storage_failure_during_processing_handled_safely(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, _ = signup(client, "proc-storage-failure@example.com")
    document = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)

    provider = get_storage_provider()

    def boom(*, key: str):
        raise StorageUnavailable("simulated outage with internal vendor detail XYZ-123")

    monkeypatch.setattr(provider, "download", boom)

    response = trigger_processing(client, token, document["id"])

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "processing_unavailable"
    assert "XYZ-123" not in response.text


# 43. resource limits reject pathological input safely
def test_pdf_exceeding_configured_page_limit_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "processing_max_pdf_pages", 1)
    token, _ = signup(client, "proc-resource-limit-pdf@example.com")
    document = upload_and_get_document(
        client, token, filename="doc.pdf",
        content=build_native_text_pdf_bytes(["Page one.", "Page two."]),
    )

    response = trigger_processing(client, token, document["id"])

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "resource_limit_exceeded"


def test_xlsx_exceeding_configured_sheet_limit_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "processing_max_xlsx_sheets", 1)
    token, _ = signup(client, "proc-resource-limit-xlsx@example.com")
    two_sheet_xlsx = build_xlsx_bytes({"One": [["A"], [1]], "Two": [["B"], [2]]})
    document = upload_and_get_document(client, token, filename="two.xlsx", content=two_sheet_xlsx)

    response = trigger_processing(client, token, document["id"])

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "resource_limit_exceeded"


def test_extracted_text_exceeding_configured_limit_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "processing_max_extracted_text_chars", 10)
    token, _ = signup(client, "proc-resource-limit-text@example.com")
    document = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)

    response = trigger_processing(client, token, document["id"])

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "resource_limit_exceeded"

