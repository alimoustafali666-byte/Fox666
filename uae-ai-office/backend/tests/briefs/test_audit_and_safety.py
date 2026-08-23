from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.llm.fake_provider import FakeLLMProvider
from app.modules.audit_log.models import AuditLog
from tests.briefs.helpers import regenerate_brief
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.helpers import signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes


def test_document_and_brief_content_never_appear_in_audit_metadata(
    client: TestClient, fake_llm_provider: FakeLLMProvider, db_session: Session
) -> None:
    token, _ = signup(client, "brief-audit-no-content@example.com")
    marker = "UNIQUE_BRIEF_CONTENT_MARKER_55221"
    pdf_bytes = build_native_text_pdf_bytes([f"Contract detail. {marker}"])
    upload_process_and_index(client, token, filename="contract.pdf", content=pdf_bytes)

    response = regenerate_brief(client, token)
    assert response.status_code == 201, response.text

    rows = list(db_session.execute(select(AuditLog).where(AuditLog.action.like("brief.%"))).scalars())
    assert rows
    for row in rows:
        assert marker not in str(row.metadata_)


def test_brief_generated_action_name_on_first_generation(
    client: TestClient, fake_llm_provider: FakeLLMProvider, db_session: Session
) -> None:
    token, _ = signup(client, "brief-audit-action-generated@example.com")

    response = regenerate_brief(client, token)
    assert response.status_code == 201

    rows = list(db_session.execute(select(AuditLog).where(AuditLog.action.like("brief.%"))).scalars())
    assert len(rows) == 1
    assert rows[0].action == "brief.generated"


def test_brief_regenerated_action_name_on_second_generation(
    client: TestClient, fake_llm_provider: FakeLLMProvider, db_session: Session
) -> None:
    token, _ = signup(client, "brief-audit-action-regenerated@example.com")

    first = regenerate_brief(client, token)
    assert first.status_code == 201
    second = regenerate_brief(client, token)
    assert second.status_code == 201

    rows = list(
        db_session.execute(
            select(AuditLog).where(AuditLog.action.like("brief.%")).order_by(AuditLog.created_at.asc())
        ).scalars()
    )
    assert [row.action for row in rows] == ["brief.generated", "brief.regenerated"]


def test_audit_metadata_never_uses_forbidden_token_substring_keys(
    client: TestClient, fake_llm_provider: FakeLLMProvider, db_session: Session
) -> None:
    """Regression guard for the Step 5 sanitizer: any audit metadata key
    containing "token" as a substring is rejected outright, so usage
    counts must be recorded under a differently-named key (see
    brief_orchestrator's input_usage_count/output_usage_count).
    """
    token, _ = signup(client, "brief-audit-no-token-key@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Some contract content."])
    upload_process_and_index(client, token, filename="contract.pdf", content=pdf_bytes)

    response = regenerate_brief(client, token)
    assert response.status_code == 201

    rows = list(db_session.execute(select(AuditLog).where(AuditLog.action == "brief.generated")).scalars())
    assert rows
    for row in rows:
        assert "input_tokens" not in row.metadata_
        assert "output_tokens" not in row.metadata_
        assert "input_usage_count" in row.metadata_

