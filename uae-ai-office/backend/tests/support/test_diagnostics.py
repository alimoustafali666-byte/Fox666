import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.audit_log.sanitizer import UnsafeAuditMetadataError, sanitize_metadata
from app.modules.auth.service import (
    TenantContext,
    decode_bearer_token,
    get_tenant_context,
    get_user_from_payload,
)
from app.modules.support.diagnostics import DiagnosticsInput, build_diagnostics
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.processing.helpers import build_native_text_pdf_bytes
from tests.support.helpers import auth_header, signup

_ALLOWED_DIAGNOSTIC_KEYS = {
    "role",
    "company_id",
    "page",
    "user_agent_summary",
    "app_version",
    "document_id",
    "document_type",
    "document_status",
    "document_indexing_status",
    "document_processing_error_code",
    "document_indexing_error_code",
    "project_id",
    "project_status",
}


def _resolve_context(db_session: Session, token: str) -> TenantContext:
    payload = decode_bearer_token(token)
    user = get_user_from_payload(db_session, payload)
    return get_tenant_context(db_session, payload, user)


# 17. diagnostic metadata follows allowlist
def test_ticket_creation_accepts_full_diagnostics_payload(client: TestClient) -> None:
    token, _ = signup(client, "diag-allowlist@example.com")
    doc = upload_process_and_index(
        client, token, filename="d.pdf", content=build_native_text_pdf_bytes(["Contract text."])
    )
    project = client.post(
        "/v1/projects", json={"name": "Diag Project"}, headers=auth_header(token)
    ).json()

    payload = {
        "page": "/documents/123",
        "document_id": doc["id"],
        "project_id": project["id"],
        "user_agent_summary": "Chrome on macOS",
        "app_version": "step17-test",
    }
    ticket = client.post(
        "/v1/support/tickets",
        json={
            "category": "documents",
            "subject": "Diagnostics check",
            "description": "Checking diagnostics allowlist.",
            "diagnostics": payload,
        },
        headers=auth_header(token),
    )
    # Diagnostics aren't returned on SupportTicketPublic (no leakage
    # surface beyond what's intentionally exposed elsewhere) -- the
    # allowlist itself is verified directly against build_diagnostics'
    # real output by the test below.
    assert ticket.status_code == 201


def test_build_diagnostics_output_keys_are_all_allowlisted(client: TestClient, db_session: Session) -> None:
    token, _ = signup(client, "diag-keys@example.com")
    doc = upload_process_and_index(
        client, token, filename="d.pdf", content=build_native_text_pdf_bytes(["Contract text."])
    )
    context = _resolve_context(db_session, token)

    diagnostics = build_diagnostics(
        db_session,
        context=context,
        data=DiagnosticsInput(page="/documents", document_id=uuid.UUID(doc["id"])),
    )

    assert set(diagnostics.keys()) <= _ALLOWED_DIAGNOSTIC_KEYS


# 18. tokens/secrets cannot enter diagnostics
def test_jwt_shaped_value_is_rejected_by_diagnostics_sanitizer() -> None:
    fake_jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dQw4w9WgXcQ"
    try:
        sanitize_metadata({"user_agent_summary": fake_jwt})
        raised = False
    except UnsafeAuditMetadataError:
        raised = True
    assert raised, "a JWT-shaped value must never survive the diagnostics sanitizer"


def test_forbidden_key_name_is_rejected_by_diagnostics_sanitizer() -> None:
    try:
        sanitize_metadata({"api_key": "sk-not-a-real-key-but-shaped-like-one"})
        raised = False
    except UnsafeAuditMetadataError:
        raised = True
    assert raised


# 19. raw document content is not attached automatically
def test_document_diagnostics_never_include_raw_content(client: TestClient, db_session: Session) -> None:
    token, _ = signup(client, "diag-no-content@example.com")
    secret_content = "This exact sentence must never appear in diagnostics."
    doc = upload_process_and_index(
        client, token, filename="d.pdf", content=build_native_text_pdf_bytes([secret_content])
    )
    context = _resolve_context(db_session, token)

    diagnostics = build_diagnostics(
        db_session, context=context, data=DiagnosticsInput(document_id=uuid.UUID(doc["id"]))
    )

    serialized = str(diagnostics)
    assert secret_content not in serialized
    assert "file_name" not in diagnostics
    assert "storage_key" not in diagnostics
    assert set(diagnostics.keys()) <= _ALLOWED_DIAGNOSTIC_KEYS


def test_diagnostics_for_another_companys_document_id_are_silently_omitted(
    client: TestClient, db_session: Session
) -> None:
    token_a, _ = signup(client, "diag-cross-a@example.com", "Company A")
    doc_a = upload_process_and_index(
        client, token_a, filename="a.pdf", content=build_native_text_pdf_bytes(["Company A text."])
    )
    token_b, _ = signup(client, "diag-cross-b@example.com", "Company B")
    context_b = _resolve_context(db_session, token_b)

    diagnostics = build_diagnostics(
        db_session, context=context_b, data=DiagnosticsInput(document_id=uuid.UUID(doc_a["id"]))
    )

    assert "document_id" not in diagnostics
    assert "document_status" not in diagnostics

