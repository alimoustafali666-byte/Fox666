from fastapi.testclient import TestClient

from app.core.llm.fake_provider import FakeLLMProvider
from tests.conversations.helpers import ask, create_conversation
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.helpers import signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes


# 53. Company A cannot retrieve Company B context through the AI endpoint.
# Company A: document contains secret value A. Company B: document
# contains secret value B (semantically identical wording, different
# secret). Company B must never receive value A, Company A's chunk,
# Company A's citation, or Company A's filename/source metadata.
def test_company_b_cannot_receive_company_a_secret_via_ask(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token_a, _ = signup(client, "cross-ai-a@example.com")
    secret_a_pdf = build_native_text_pdf_bytes(
        ["The confidential project code word is FALCON-ALPHA-771."]
    )
    document_a = upload_process_and_index(
        client, token_a, filename="company-a-secret.pdf", content=secret_a_pdf
    )

    token_b, _ = signup(client, "cross-ai-b@example.com")
    secret_b_pdf = build_native_text_pdf_bytes(
        ["The confidential project code word is FALCON-BETA-992."]
    )
    document_b = upload_process_and_index(
        client, token_b, filename="company-b-secret.pdf", content=secret_b_pdf
    )

    conversation_b = create_conversation(client, token_b)
    response = ask(
        client,
        token_b,
        conversation_id=conversation_b["id"],
        question="What is the confidential project code word?",
    )

    assert response.status_code == 201
    body = response.json()

    assert "FALCON-ALPHA-771" not in body["content"]
    assert "company-a-secret.pdf" not in body["content"]

    for citation in body["citations"]:
        assert citation["document_id"] == document_b["id"]
        assert citation["document_id"] != document_a["id"]
        assert citation["file_name"] == "company-b-secret.pdf"

    # And the provider itself was only ever handed company B's content.
    request = fake_llm_provider.calls[-1]
    for item in request.document_context:
        assert "FALCON-ALPHA-771" not in item.content
        assert "company-a-secret.pdf" not in item.content


# INSUFFICIENT-INFORMATION TEST, exactly as specified: a document about
# payment terms exists; asking about 2027 revenue (which no document
# discusses) must never invent an answer.
def test_asking_about_unrelated_topic_never_invents_an_answer(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "insufficient-scenario@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])
    upload_process_and_index(client, token, filename="terms.pdf", content=pdf_bytes)
    conversation = create_conversation(client, token)

    response = ask(
        client, token, conversation_id=conversation["id"], question="What is the company's 2027 revenue?"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is False
    assert body["citations"] == []
    assert "revenue" not in body["content"].lower() or "enough information" in body["content"].lower()
    # Below-threshold retrieval means Claude is never even called for this
    # off-topic question.
    assert fake_llm_provider.calls == []

