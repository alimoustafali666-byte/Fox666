import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm.fake_provider import FakeLLMProvider
from app.db.session import set_company_context
from app.modules.briefs import repository as briefs_repository
from tests.briefs.helpers import regenerate_brief
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.helpers import signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes


# incremental window: only documents updated since the last brief are
# ever considered -- proven by seeding a real previous brief (via the
# repository, exactly as brief_orchestrator would have persisted it) and
# checking a document uploaded *before* that brief never reaches the
# provider on the next regeneration, only one uploaded *after* it does.
def test_incremental_window_excludes_documents_covered_by_previous_brief(
    client: TestClient, fake_llm_provider: FakeLLMProvider, db_session: Session
) -> None:
    token, claims = signup(client, "brief-window@example.com")
    company_id = uuid.UUID(claims["company_id"])
    user_id = uuid.UUID(claims["sub"])

    old_pdf = build_native_text_pdf_bytes(["Old document about a drainage inspection."])
    upload_process_and_index(client, token, filename="old.pdf", content=old_pdf)

    set_company_context(db_session, company_id)
    briefs_repository.create_daily_brief(
        db_session, id=uuid.uuid4(), company_id=company_id, generated_by=user_id,
        brief_date=(datetime.now(UTC) - timedelta(days=1)).date(), summary="previous brief",
    )

    new_pdf = build_native_text_pdf_bytes(["New document about a signed change order."])
    upload_process_and_index(client, token, filename="new.pdf", content=new_pdf)

    response = regenerate_brief(client, token)

    assert response.status_code == 201, response.text
    assert len(fake_llm_provider.brief_calls) == 1
    call = fake_llm_provider.brief_calls[0]
    assert len(call.new_documents) == 1
    assert "change order" in call.new_documents[0].content
    assert "drainage" not in call.new_documents[0].content


# carry-forward: a non-"new_information" item from a previous brief is
# handed to the provider as context on the next generation call.
def test_carry_forward_items_from_previous_brief_are_passed_to_provider(
    client: TestClient, fake_llm_provider: FakeLLMProvider, db_session: Session
) -> None:
    token, claims = signup(client, "brief-carry-forward@example.com")
    company_id = uuid.UUID(claims["company_id"])
    user_id = uuid.UUID(claims["sub"])

    set_company_context(db_session, company_id)
    previous_brief = briefs_repository.create_daily_brief(
        db_session, id=uuid.uuid4(), company_id=company_id, generated_by=user_id,
        brief_date=(datetime.now(UTC) - timedelta(days=1)).date(), summary="previous brief",
    )
    briefs_repository.create_brief_items(
        db_session, company_id=company_id, brief_id=previous_brief.id,
        items=[
            {
                "category": "pending_action",
                "text": "Awaiting client sign-off on variation order #12.",
                "priority": 1,
                "source_document_id": None,
            }
        ],
    )

    response = regenerate_brief(client, token)

    assert response.status_code == 201, response.text
    assert len(fake_llm_provider.brief_calls) == 1
    call = fake_llm_provider.brief_calls[0]
    assert len(call.carry_forward_items) == 1
    assert call.carry_forward_items[0].category == "pending_action"
    assert "variation order #12" in call.carry_forward_items[0].text

    body = response.json()
    assert any(item["category"] == "pending_action" for item in body["items"])


# document count and per-document content are bounded per the approved
# architecture -- brief_max_documents_per_run and
# brief_max_chars_per_document keep a large backlog from producing an
# unbounded prompt.
def test_documents_per_run_are_bounded(
    client: TestClient, fake_llm_provider: FakeLLMProvider, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "brief_max_documents_per_run", 2)
    token, _ = signup(client, "brief-doc-bound@example.com")
    for i in range(4):
        pdf = build_native_text_pdf_bytes([f"Document number {i} content."])
        upload_process_and_index(client, token, filename=f"doc-{i}.pdf", content=pdf)

    response = regenerate_brief(client, token)

    assert response.status_code == 201, response.text
    assert len(fake_llm_provider.brief_calls) == 1
    assert len(fake_llm_provider.brief_calls[0].new_documents) == 2


def test_document_content_is_truncated_to_configured_char_limit(
    client: TestClient, fake_llm_provider: FakeLLMProvider, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "brief_max_chars_per_document", 50)
    token, _ = signup(client, "brief-char-bound@example.com")
    pdf = build_native_text_pdf_bytes(["X" * 500])
    upload_process_and_index(client, token, filename="long.pdf", content=pdf)

    response = regenerate_brief(client, token)

    assert response.status_code == 201, response.text
    content = fake_llm_provider.brief_calls[0].new_documents[0].content
    assert content.count("X") <= 50

