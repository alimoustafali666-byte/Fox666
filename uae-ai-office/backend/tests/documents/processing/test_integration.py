import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import set_company_context
from app.modules.audit_log.models import AuditLog
from app.modules.documents.models import DocumentChunk
from tests.documents.helpers import auth_header, create_project, signup, upload_file
from tests.documents.processing.helpers import (
    build_boq_xlsx_bytes,
    build_native_text_pdf_bytes,
    trigger_processing,
)


def test_pdf_processing_happy_path_and_cross_company_isolation(
    client: TestClient, db_session: Session
) -> None:
    # signup -> login (signup returns an access token directly, same as
    # every other integration test in this suite) -> create project
    token, claims = signup(client, "proc-integration-pdf@example.com", "Integration Processing Co")
    company_id = uuid.UUID(claims["company_id"])
    project = create_project(client, token, name="Processing Project")

    # -> upload a small native-text PDF to project
    pdf_bytes = build_native_text_pdf_bytes(
        ["Contract terms and conditions, page one.", "Payment schedule, page two."]
    )
    upload_response = upload_file(
        client, token, filename="contract.pdf", content=pdf_bytes,
        project_id=project["id"], document_type="contract",
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    # -> process document -> status becomes processed
    process_response = trigger_processing(client, token, document_id)
    assert process_response.status_code == 200, process_response.text
    assert process_response.json()["status"] == "processed"

    # -> document_chunks created, contain expected text, page metadata exists
    set_company_context(db_session, company_id)
    chunks = list(
        db_session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == uuid.UUID(document_id))
            .order_by(DocumentChunk.chunk_index.asc())
        ).scalars()
    )
    assert len(chunks) > 0
    all_text = " ".join(c.content for c in chunks)
    assert "Contract terms" in all_text
    assert "Payment schedule" in all_text
    assert all(c.page_number is not None for c in chunks)
    # Both pages are short enough to land in the same chunk (chunking
    # targets a token budget, not one chunk per page) -- page_number
    # reflects the chunk's first page, and source_location.pages carries
    # the full set for citation purposes.
    all_pages = {p for c in chunks for p in (c.source_location or {}).get("pages", [])}
    assert all_pages == {1, 2}

    # -> audit events exist
    set_company_context(db_session, company_id)
    actions = list(
        db_session.execute(select(AuditLog.action).order_by(AuditLog.created_at.asc())).scalars()
    )
    assert "document.processing_started" in actions
    assert "document.processing_succeeded" in actions

    # --- second company cannot access/process/read chunks ---
    other_token, _ = signup(client, "proc-integration-outsider@example.com", "Other Processing Co")

    assert (
        client.post(f"/v1/documents/{document_id}/process", headers=auth_header(other_token)).status_code
        == 404
    )
    assert client.get(f"/v1/documents/{document_id}", headers=auth_header(other_token)).status_code == 404

    other_claims_response = client.get("/v1/auth/me", headers=auth_header(other_token))
    other_company_id = uuid.UUID(other_claims_response.json()["company_id"])
    set_company_context(db_session, other_company_id)
    other_visible_chunks = db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(document_id))
    ).all()
    assert other_visible_chunks == []


def test_xlsx_boq_processing_preserves_structure(client: TestClient, db_session: Session) -> None:
    # upload a small BOQ-style workbook
    token, claims = signup(client, "proc-integration-xlsx@example.com", "BOQ Processing Co")
    company_id = uuid.UUID(claims["company_id"])

    upload_response = upload_file(
        client, token, filename="boq.xlsx", content=build_boq_xlsx_bytes(), document_type="boq"
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    # -> process
    process_response = trigger_processing(client, token, document_id)
    assert process_response.status_code == 200, process_response.text
    assert process_response.json()["status"] == "processed"

    set_company_context(db_session, company_id)
    chunks = list(
        db_session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == uuid.UUID(document_id))
            .order_by(DocumentChunk.chunk_index.asc())
        ).scalars()
    )
    assert len(chunks) > 0

    # -> verify sheet/row structure is retained
    assert all(c.sheet_name == "BOQ" for c in chunks)
    assert all(c.source_location and c.source_location.get("sheet_name") == "BOQ" for c in chunks)

    all_text = " ".join(c.content for c in chunks)
    # -> verify numeric values survive exactly
    assert "Qty: 50" in all_text
    assert "Rate: 350" in all_text
    assert "Rate: 2800.75" in all_text
    assert "Amount: 17500" in all_text
    assert "Amount: 29408.25" in all_text
    assert "2026-01-15" in all_text  # date preserved

    # -> verify chunks have correct sheet metadata (already asserted above);
    # also confirm rows never merged with a different sheet's content
    assert "Summary" not in all_text

