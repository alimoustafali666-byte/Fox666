from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.llm.fake_provider import FakeLLMProvider
from app.core.llm.provider import GroundedAnswerCitation, GroundedAnswerResult
from app.modules.audit_log.models import AuditLog
from tests.conversations.helpers import ask, create_conversation
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.helpers import seed_member, signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes


def _valid_answer() -> GroundedAnswerResult:
    return GroundedAnswerResult(
        answer="A very specific secret answer text XYZQ123.",
        sufficient=True,
        citations=[GroundedAnswerCitation(ref="1")],
        model_identifier="fake-llm-v1",
        input_tokens=20,
        output_tokens=6,
    )


# 51. user question not placed in audit metadata
# 52. Claude answer not placed in audit metadata
def test_question_and_answer_text_never_appear_in_audit_metadata(
    client: TestClient, fake_llm_provider: FakeLLMProvider, db_session: Session
) -> None:
    token, _ = signup(client, "audit-no-content@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])
    upload_process_and_index(client, token, filename="terms.pdf", content=pdf_bytes)
    conversation = create_conversation(client, token)
    fake_llm_provider.enqueue(_valid_answer())

    question_marker = "UNIQUE_QUESTION_MARKER_998877"
    response = ask(
        client, token, conversation_id=conversation["id"], question=f"What are the terms? {question_marker}"
    )
    assert response.status_code == 201

    rows = list(db_session.execute(select(AuditLog).where(AuditLog.action.like("ai.%"))).scalars())
    assert rows
    for row in rows:
        serialized = str(row.metadata_)
        assert question_marker not in serialized
        assert "XYZQ123" not in serialized
        assert "secret answer" not in serialized


def test_insufficient_information_audit_event_never_contains_question_text(
    client: TestClient, fake_llm_provider: FakeLLMProvider, db_session: Session
) -> None:
    token, _ = signup(client, "audit-insufficient-no-content@example.com")
    conversation = create_conversation(client, token)

    marker = "UNIQUE_INSUFFICIENT_MARKER_11223"
    ask(client, token, conversation_id=conversation["id"], question=f"What is X? {marker}")

    rows = list(
        db_session.execute(
            select(AuditLog).where(AuditLog.action == "ai.question_insufficient")
        ).scalars()
    )
    assert rows
    for row in rows:
        assert marker not in str(row.metadata_)


# 54. all four roles can ask against readable company documents
def test_all_four_roles_can_ask_against_readable_documents(
    client: TestClient, fake_llm_provider: FakeLLMProvider, db_session: Session
) -> None:
    import uuid

    token_owner, claims = signup(client, "rbac-owner@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])
    upload_process_and_index(client, token_owner, filename="terms.pdf", content=pdf_bytes)
    company_id = uuid.UUID(claims["company_id"])

    for role in ("admin", "manager", "member"):
        role_token = seed_member(db_session, company_id=company_id, email=f"rbac-{role}@example.com", role=role)
        conversation_response = client.post(
            "/v1/conversations", json={}, headers={"Authorization": f"Bearer {role_token}"}
        )
        assert conversation_response.status_code == 201, role
        conversation_id = conversation_response.json()["id"]

        fake_llm_provider.enqueue(_valid_answer())
        response = ask(
            client, role_token, conversation_id=conversation_id, question="What are the payment terms?"
        )
        assert response.status_code == 201, (role, response.text)

