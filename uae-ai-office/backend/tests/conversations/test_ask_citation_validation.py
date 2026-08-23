from fastapi.testclient import TestClient

from app.core.llm.exceptions import LLMMalformedOutputError
from app.core.llm.fake_provider import FakeLLMProvider
from app.core.llm.provider import GroundedAnswerCitation, GroundedAnswerResult
from tests.conversations.helpers import ask, create_conversation
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.helpers import signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes


def _setup(client: TestClient, email: str):
    token, _ = signup(client, email)
    pdf_bytes = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])
    document = upload_process_and_index(client, token, filename="terms.pdf", content=pdf_bytes)
    conversation = create_conversation(client, token)
    return token, document, conversation


def _valid_answer(ref: str = "1") -> GroundedAnswerResult:
    return GroundedAnswerResult(
        answer="Payment terms are 30 days net.",
        sufficient=True,
        citations=[GroundedAnswerCitation(ref=ref)],
        model_identifier="fake-llm-v1",
        input_tokens=20,
        output_tokens=6,
    )


# 27. structured output parsed safely
# 28. malformed output rejected
def test_malformed_structured_output_triggers_retry_then_safe_fallback(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _document, conversation = _setup(client, "cite-malformed@example.com")
    fake_llm_provider.enqueue_error(LLMMalformedOutputError("bad json"))
    fake_llm_provider.enqueue_error(LLMMalformedOutputError("still bad"))

    response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is False
    assert body["citations"] == []
    # exactly one corrective retry -- two attempts total, never a loop
    assert len(fake_llm_provider.calls) == 2
    assert fake_llm_provider.calls[1].corrective_note is not None


def test_malformed_output_recovers_on_corrective_retry(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _document, conversation = _setup(client, "cite-malformed-recover@example.com")
    fake_llm_provider.enqueue_error(LLMMalformedOutputError("bad json"))
    fake_llm_provider.enqueue(_valid_answer())

    response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is True
    assert len(body["citations"]) == 1
    assert len(fake_llm_provider.calls) == 2


# 29. valid citation accepted
def test_valid_citation_is_accepted_and_persisted(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, document, conversation = _setup(client, "cite-valid@example.com")
    fake_llm_provider.enqueue(_valid_answer(ref="1"))

    response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is True
    assert len(body["citations"]) == 1
    assert body["citations"][0]["document_id"] == document["id"]


# 30. fabricated chunk citation rejected
def test_fabricated_citation_ref_is_rejected_and_retried(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _document, conversation = _setup(client, "cite-fabricated@example.com")
    fake_llm_provider.enqueue(
        GroundedAnswerResult(
            answer="Payment terms are 30 days net.",
            sufficient=True,
            citations=[GroundedAnswerCitation(ref="999")],  # never given to the model
            model_identifier="fake-llm-v1",
            input_tokens=20,
            output_tokens=6,
        )
    )
    fake_llm_provider.enqueue_error(LLMMalformedOutputError("still bad"))  # simulate no recovery

    response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is False
    assert body["citations"] == []
    assert len(fake_llm_provider.calls) == 2


# 32. citation to non-retrieved chunk rejected -- same mechanism as
# fabricated, since a ref is only ever valid if the caller actually
# handed it out in THIS request's document_context.
def test_citation_to_a_ref_outside_this_requests_context_is_rejected(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _document, conversation = _setup(client, "cite-outside-context@example.com")
    fake_llm_provider.enqueue(_valid_answer(ref="1"))
    fake_llm_provider.enqueue(
        GroundedAnswerResult(
            answer="Payment terms are 30 days net.",
            sufficient=True,
            citations=[GroundedAnswerCitation(ref="7")],
            model_identifier="fake-llm-v1",
            input_tokens=20,
            output_tokens=6,
        )
    )

    response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")
    assert response.status_code == 201
    assert response.json()["is_sufficient"] is True  # first (valid) attempt used

    # A second, independent question where the only scripted response has
    # an out-of-range ref -- exhausts the retry budget -> safe fallback.
    fake_llm_provider.enqueue(
        GroundedAnswerResult(
            answer="whatever",
            sufficient=True,
            citations=[GroundedAnswerCitation(ref="7")],
            model_identifier="fake-llm-v1",
            input_tokens=1,
            output_tokens=1,
        )
    )
    fake_llm_provider.enqueue(
        GroundedAnswerResult(
            answer="whatever",
            sufficient=True,
            citations=[GroundedAnswerCitation(ref="7")],
            model_identifier="fake-llm-v1",
            input_tokens=1,
            output_tokens=1,
        )
    )
    response2 = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")
    assert response2.json()["is_sufficient"] is False
    assert response2.json()["citations"] == []


# 31. cross-company citation rejected -- structurally impossible here: a
# citation ref only ever maps to a chunk from THIS company's own
# retrieval results (refs are built fresh per-request from
# retrieval_service, which is itself company-scoped + RLS-enforced), so
# there is no ref value the model could return that resolves to another
# company's chunk. See tests/db/test_conversations_isolation.py and
# test_cross_tenant_ai.py for the end-to-end proof of that isolation.


# 33. citation to deleted document rejected
def test_citation_to_a_since_deleted_document_is_excluded_from_response(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, document, conversation = _setup(client, "cite-deleted-doc@example.com")
    fake_llm_provider.enqueue(_valid_answer(ref="1"))

    from tests.documents.helpers import auth_header

    delete_response = client.delete(f"/v1/documents/{document['id']}", headers=auth_header(token))
    assert delete_response.status_code == 200

    # Retrieval itself already excludes soft-deleted documents' chunks
    # (Step 10), so this becomes the "no relevant chunks" path -- Claude
    # is never even called for a now-inaccessible document.
    response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")
    assert response.status_code == 201
    assert response.json()["is_sufficient"] is False
    assert fake_llm_provider.calls == []


# 34. duplicate citations normalized
def test_duplicate_citations_are_normalized(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _document, conversation = _setup(client, "cite-duplicate@example.com")
    fake_llm_provider.enqueue(
        GroundedAnswerResult(
            answer="Payment terms are 30 days net.",
            sufficient=True,
            citations=[
                GroundedAnswerCitation(ref="1"),
                GroundedAnswerCitation(ref="1"),
                GroundedAnswerCitation(ref="1"),
            ],
            model_identifier="fake-llm-v1",
            input_tokens=20,
            output_tokens=6,
        )
    )

    response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")

    assert response.status_code == 201
    assert len(response.json()["citations"]) == 1


# 35. sufficient=true requires valid citation
def test_sufficient_true_with_zero_citations_is_rejected(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _document, conversation = _setup(client, "cite-no-citation@example.com")
    fake_llm_provider.enqueue(
        GroundedAnswerResult(
            answer="Payment terms are 30 days net.",
            sufficient=True,
            citations=[],
            model_identifier="fake-llm-v1",
            input_tokens=20,
            output_tokens=6,
        )
    )
    fake_llm_provider.enqueue_error(LLMMalformedOutputError("still no citation"))

    response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is False
    assert body["citations"] == []


# 44. retries bounded
# 45. corrective citation retry happens at most once
def test_retries_are_bounded_to_configured_maximum(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _document, conversation = _setup(client, "cite-bounded-retry@example.com")
    for _ in range(5):
        fake_llm_provider.enqueue_error(LLMMalformedOutputError("always bad"))

    response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")

    assert response.status_code == 201
    assert response.json()["is_sufficient"] is False
    # ask_max_citation_retries=1 by default -> exactly 2 attempts, not 5.
    assert len(fake_llm_provider.calls) == 2

