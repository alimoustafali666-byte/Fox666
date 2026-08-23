from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.llm.fake_provider import FakeLLMProvider
from app.core.llm.provider import GroundedAnswerCitation, GroundedAnswerResult
from tests.conversations.helpers import ask, create_conversation, list_messages
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.helpers import signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes


# 12. retrieval service is used
def test_ask_uses_retrieval_service(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _ = signup(client, "ask-retrieval-used@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])
    upload_process_and_index(client, token, filename="terms.pdf", content=pdf_bytes)
    conversation = create_conversation(client, token)

    response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")

    assert response.status_code == 201
    assert len(fake_llm_provider.calls) == 1
    request = fake_llm_provider.calls[0]
    assert any("Payment terms" in item.content for item in request.document_context)


# 13. retrieval threshold cannot be bypassed
def test_unrelated_document_below_threshold_is_not_passed_to_llm(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "ask-threshold@example.com")
    unrelated = build_native_text_pdf_bytes(["Xylophone quokka umbrella zeppelin marmalade jigsaw."])
    upload_process_and_index(client, token, filename="unrelated.pdf", content=unrelated)
    conversation = create_conversation(client, token)

    response = ask(
        client,
        token,
        conversation_id=conversation["id"],
        question="concrete foundation steel reinforcement schedule",
    )

    assert response.status_code == 201
    assert response.json()["is_sufficient"] is False
    assert fake_llm_provider.calls == []


# 14. zero relevant chunks => insufficient
# 15. zero relevant chunks => Claude NOT called
# 16. insufficient response has no citations
def test_no_documents_at_all_returns_insufficient_without_calling_llm(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "ask-no-docs@example.com")
    conversation = create_conversation(client, token)

    response = ask(client, token, conversation_id=conversation["id"], question="What is our 2027 revenue?")

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is False
    assert body["content"] == "I don't have enough information in the available documents."
    assert body["citations"] == []
    assert fake_llm_provider.calls == []


# 17. insufficient response persisted
def test_insufficient_response_is_persisted(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _ = signup(client, "ask-insufficient-persist@example.com")
    conversation = create_conversation(client, token)

    ask(client, token, conversation_id=conversation["id"], question="What is our 2027 revenue?")

    # Newest-first, matching every other paginated list endpoint in this
    # API (documents, conversations) -- the assistant reply comes second
    # chronologically, so it's messages[0] here.
    messages = list_messages(client, token, conversation["id"]).json()["items"]
    assert len(messages) == 2
    assert messages[0]["role"] == "assistant"
    assert messages[1]["role"] == "user"
    assert messages[0]["is_sufficient"] is False


# 18. valid retrieval calls Claude
# 19. Claude receives only selected context
# 20. Claude does not receive storage_key
# 21. Claude does not receive embeddings
def test_llm_receives_only_selected_chunk_content_never_storage_key_or_embedding(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "ask-context-shape@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Contract Value: AED 125000 for the concrete works."])
    upload_process_and_index(client, token, filename="contract.pdf", content=pdf_bytes)
    conversation = create_conversation(client, token)

    response = ask(client, token, conversation_id=conversation["id"], question="What is the contract value?")

    assert response.status_code == 201
    assert len(fake_llm_provider.calls) == 1
    request = fake_llm_provider.calls[0]
    assert len(request.document_context) >= 1
    for item in request.document_context:
        assert "storage_key" not in item.content
        assert not hasattr(item, "storage_key")
        assert not hasattr(item, "embedding")
        # refs are small provider-neutral aliases, never raw chunk UUIDs
        assert len(item.ref) <= 4
        int(item.ref)  # a plain small integer string, not a UUID


# 22. system prompt separates instructions/context
# 23. prompt explicitly treats documents as data
def test_system_prompt_is_never_sent_as_document_context_and_never_persisted(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    """The FakeLLMProvider never receives a system prompt at all (Claude's
    top-level `system` parameter is constructed only inside
    AnthropicClaudeProvider, structurally separate from the request this
    test inspects) -- proving document_context/question/history are the
    ONLY things ask_service hands to the provider abstraction, and that
    nothing resembling the system instructions ends up in a persisted
    message.
    """
    token, _ = signup(client, "ask-system-prompt@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Contract Value: AED 125000 for the concrete works."])
    upload_process_and_index(client, token, filename="contract.pdf", content=pdf_bytes)
    conversation = create_conversation(client, token)

    ask(client, token, conversation_id=conversation["id"], question="What is the contract value?")

    request = fake_llm_provider.calls[0]
    assert not hasattr(request, "system")
    assert not hasattr(request, "system_prompt")

    messages = list_messages(client, token, conversation["id"]).json()["items"]
    for message in messages:
        assert "You are the" not in message["content"]
        assert "DOCUMENT CONTEXT" not in message["content"]


def test_ask_respects_document_id_filter(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _ = signup(client, "ask-doc-filter@example.com")
    matching = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])
    other = build_native_text_pdf_bytes(["Payment terms: 60 days net for supplier X."])
    doc_a = upload_process_and_index(client, token, filename="a.pdf", content=matching)
    upload_process_and_index(client, token, filename="b.pdf", content=other)
    conversation = create_conversation(client, token)

    fake_llm_provider.enqueue(
        GroundedAnswerResult(
            answer="30 days net.",
            sufficient=True,
            citations=[GroundedAnswerCitation(ref="1")],
            model_identifier="fake-llm-v1",
            input_tokens=10,
            output_tokens=5,
        )
    )

    response = ask(
        client,
        token,
        conversation_id=conversation["id"],
        question="What are the payment terms?",
        document_id=doc_a["id"],
    )

    assert response.status_code == 201
    assert response.json()["citations"][0]["document_id"] == doc_a["id"]


def test_ask_default_top_k_matches_configured_default(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "ask-topk@example.com")
    for i in range(settings.retrieval_top_k_default + 3):
        pdf_bytes = build_native_text_pdf_bytes([f"widget entry number {i} details schedule."])
        upload_process_and_index(client, token, filename=f"doc-{i}.pdf", content=pdf_bytes)
    conversation = create_conversation(client, token)

    ask(client, token, conversation_id=conversation["id"], question="widget entry details schedule")

    request = fake_llm_provider.calls[0]
    assert len(request.document_context) == settings.retrieval_top_k_default

