from fastapi.testclient import TestClient

from app.core.llm.fake_provider import FakeLLMProvider
from app.core.llm.provider import GroundedAnswerCitation, GroundedAnswerResult
from tests.conversations.helpers import ask, create_conversation, list_messages
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.helpers import signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes


def _valid_answer(ref: str = "1") -> GroundedAnswerResult:
    return GroundedAnswerResult(
        answer="Payment terms are 30 days net.",
        sufficient=True,
        citations=[GroundedAnswerCitation(ref=ref)],
        model_identifier="fake-llm-v1",
        input_tokens=20,
        output_tokens=6,
    )


# 36. assistant answer persisted
# 37. exact message_citation rows persisted
def test_assistant_answer_and_citation_rows_are_persisted(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "persist-answer@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])
    document = upload_process_and_index(client, token, filename="terms.pdf", content=pdf_bytes)
    conversation = create_conversation(client, token)
    fake_llm_provider.enqueue(_valid_answer())

    ask_response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")
    assistant_id = ask_response.json()["id"]

    messages = list_messages(client, token, conversation["id"]).json()["items"]
    assistant_row = next(m for m in messages if m["id"] == assistant_id)
    assert assistant_row["content"] == "Payment terms are 30 days net."
    assert assistant_row["role"] == "assistant"
    assert len(assistant_row["citations"]) == 1
    assert assistant_row["citations"][0]["document_id"] == document["id"]


# 38. citation source metadata returned
def test_citation_source_metadata_is_returned(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _ = signup(client, "persist-metadata@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])
    document = upload_process_and_index(client, token, filename="terms.pdf", content=pdf_bytes, document_type="contract")
    conversation = create_conversation(client, token)
    fake_llm_provider.enqueue(_valid_answer())

    response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")

    citation = response.json()["citations"][0]
    assert citation["document_id"] == document["id"]
    assert citation["file_name"] == "terms.pdf"
    assert citation["document_type"] == "contract"
    assert citation["page_number"] == 1
    assert "document_chunk_id" in citation


# 39. storage_key never returned
# 40. vectors never returned
def test_response_never_contains_storage_key_or_vector(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "persist-no-secrets@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])
    upload_process_and_index(client, token, filename="terms.pdf", content=pdf_bytes)
    conversation = create_conversation(client, token)
    fake_llm_provider.enqueue(_valid_answer())

    response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")

    assert "storage_key" not in response.text
    assert "embedding" not in response.text
    for citation in response.json()["citations"]:
        assert "storage_key" not in citation
        assert "embedding" not in citation
        assert "signed_url" not in citation
        assert "download_url" not in citation


# 41. API key never logged
def test_api_key_never_appears_in_provider_repr_or_logs(client: TestClient) -> None:
    from app.core.llm.anthropic_provider import AnthropicClaudeProvider

    provider = AnthropicClaudeProvider(
        api_key="sk-ant-super-secret-value",
        model="claude-sonnet-5",
        max_output_tokens=100,
        brief_max_output_tokens=200,
        insights_max_output_tokens=200,
        timeout_seconds=5.0,
        max_retries=1,
    )
    assert "sk-ant-super-secret-value" not in repr(provider)
    assert "sk-ant-super-secret-value" not in str(provider)


# 46. conversation history bounded
def test_conversation_history_passed_to_llm_is_bounded(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    from app.core.config import settings

    token, _ = signup(client, "history-bounded@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])
    upload_process_and_index(client, token, filename="terms.pdf", content=pdf_bytes)
    conversation = create_conversation(client, token)

    for _ in range(5):
        fake_llm_provider.enqueue(_valid_answer())
        ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")

    fake_llm_provider.enqueue(_valid_answer())
    ask(client, token, conversation_id=conversation["id"], question="When is the first payment due?")

    last_request = fake_llm_provider.calls[-1]
    assert len(last_request.history) <= settings.ask_max_history_turns * 2


# 47. prior assistant answer is not treated as factual document source
def test_prior_assistant_answer_is_history_not_document_context(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "history-not-fact@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])
    upload_process_and_index(client, token, filename="terms.pdf", content=pdf_bytes)
    conversation = create_conversation(client, token)

    fake_llm_provider.enqueue(
        GroundedAnswerResult(
            answer="A hallucinated made-up fact about revenue.",
            sufficient=True,
            citations=[GroundedAnswerCitation(ref="1")],
            model_identifier="fake-llm-v1",
            input_tokens=1,
            output_tokens=1,
        )
    )
    ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")

    fake_llm_provider.enqueue(_valid_answer())
    ask(client, token, conversation_id=conversation["id"], question="When is the first payment due?")

    second_request = fake_llm_provider.calls[-1]
    # the hallucinated prior answer may appear in `history` (plain
    # conversational context) but never inside document_context, which is
    # the only thing this module treats as a factual source.
    assert all(
        "hallucinated" not in item.content for item in second_request.document_context
    )


# 48. follow-up still performs fresh retrieval
def test_followup_question_performs_fresh_retrieval(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "history-fresh-retrieval@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])
    upload_process_and_index(client, token, filename="terms.pdf", content=pdf_bytes)
    conversation = create_conversation(client, token)

    fake_llm_provider.enqueue(_valid_answer())
    ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")
    first_context = fake_llm_provider.calls[-1].document_context

    fake_llm_provider.enqueue(_valid_answer())
    ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")
    second_context = fake_llm_provider.calls[-1].document_context

    assert len(fake_llm_provider.calls) == 2
    assert first_context and second_context
    assert first_context[0].content == second_context[0].content


# 49. model identifier stored
# 50. token usage stored
def test_model_identifier_and_token_usage_are_stored(
    client: TestClient, fake_llm_provider: FakeLLMProvider, db_session
) -> None:
    from sqlalchemy import select

    from app.modules.conversations.models import Message

    token, _ = signup(client, "persist-tokens@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])
    upload_process_and_index(client, token, filename="terms.pdf", content=pdf_bytes)
    conversation = create_conversation(client, token)
    fake_llm_provider.enqueue(_valid_answer())

    ask_response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")
    assert ask_response.json()["model_identifier"] == "fake-llm-v1"

    assistant_id = ask_response.json()["id"]
    row = db_session.execute(select(Message).where(Message.id == assistant_id)).scalar_one()
    assert row.model_identifier == "fake-llm-v1"
    assert row.input_tokens == 20
    assert row.output_tokens == 6

