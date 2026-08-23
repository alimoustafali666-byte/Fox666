"""Requirement 6 (Step 14): Arabic prompt-injection/adversarial text
verified to remain inert document data.

Mirrors tests/conversations/test_prompt_injection.py's design exactly,
in Arabic: DocumentChunk.content is data, never instructions (see
app.modules.documents.models.DocumentChunk's own docstring), and
GroundedAnswerRequest has no separate "instructions" channel a document
could reach into -- structurally, injected text can only ever arrive as
DocumentContextItem.content, indistinguishable (to the provider) from
any other retrieved text.

document_id scoping targets the adversarial document specifically (see
tests/arabic_rag/fixtures.py's module docstring on why cross-document bag-
of-words competition would otherwise decide which document "wins" for a
generic question, independent of the adversarial-injection question this
test is actually about).
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.llm.fake_provider import FakeLLMProvider
from app.core.llm.provider import GroundedAnswerCitation, GroundedAnswerResult
from tests.arabic_rag.fixtures import INJECTION_SENTENCE_AR, contract_adversarial_arabic
from tests.arabic_rag.helpers import all_chunk_content, upload_fixture
from tests.conversations.helpers import ask, create_conversation
from tests.documents.helpers import signup


def test_arabic_injection_text_is_persisted_verbatim_as_inert_data(
    client: TestClient, db_session: Session
) -> None:
    """Proves the injected Arabic instruction text is stored, unmodified
    and unstripped, exactly like any other document content -- the
    pipeline does not (and structurally cannot) special-case or execute
    it at the parsing/storage layer.
    """
    token, _ = signup(client, "arabic-injection-stored@example.com")
    document = upload_fixture(client, token, contract_adversarial_arabic())

    persisted = all_chunk_content(db_session, document["id"])

    assert INJECTION_SENTENCE_AR in persisted
    assert "AED 125,000" in persisted  # the real value is also present, unremoved


def test_arabic_injection_reaches_the_provider_only_as_document_context(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    """The DEFAULT (unscripted) FakeLLMProvider grounding does word-
    overlap selection and then echoes the whole matched context item's
    content verbatim (see its module docstring) -- it has no "extract
    just the value" intelligence, so since this fixture's injection
    sentence and real value share one short chunk (see
    contract_adversarial_arabic's docstring), the echoed answer
    legitimately contains both. That is a property of this mechanical
    echo behavior, not of the injection having gained any authority --
    the actual "does the injection change what the model does" property
    is tested properly below, against a SCRIPTED correct answer (exactly
    matching tests/conversations/test_prompt_injection.py's own
    pattern). What this test proves instead: retrieval still correctly
    finds and cites the real document despite the injected text sharing
    its chunk, and the injected text reaches the provider through
    GroundedAnswerRequest.document_context and nowhere else -- there is
    no separate "instructions" channel on the request it could have
    reached instead.
    """
    token, _ = signup(client, "arabic-injection-default@example.com")
    document = upload_fixture(client, token, contract_adversarial_arabic())
    conversation = create_conversation(client, token)

    response = ask(
        client, token, conversation_id=conversation["id"],
        document_id=document["id"], question="ما قيمة هذا العقد؟",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is True
    assert "125,000" in body["content"]
    assert body["citations"][0]["document_id"] == document["id"]

    request = fake_llm_provider.calls[0]
    assert any(INJECTION_SENTENCE_AR in item.content for item in request.document_context)


def test_arabic_injection_cannot_override_a_correctly_behaving_model(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    """When the model behaves correctly (scripted here via enqueue(...)
    to return the real, correctly-cited answer -- standing in for what
    the Step 11 system prompt requires of the real Claude model), the
    pipeline grounds and persists that answer end-to-end, citing the real
    document, never a fabricated value -- even though the injected
    instruction text was delivered to the provider right alongside it.
    """
    token, _ = signup(client, "arabic-injection-scripted@example.com")
    document = upload_fixture(client, token, contract_adversarial_arabic())
    conversation = create_conversation(client, token)
    fake_llm_provider.enqueue(
        GroundedAnswerResult(
            answer="قيمة العقد هي AED 125,000.",
            sufficient=True,
            citations=[GroundedAnswerCitation(ref="1")],
            model_identifier="fake-llm-v1",
            input_tokens=42,
            output_tokens=8,
        )
    )

    response = ask(
        client, token, conversation_id=conversation["id"],
        document_id=document["id"], question="ما قيمة هذا العقد؟",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is True
    assert "125,000" in body["content"]
    assert "999,999,999" not in body["content"]
    assert len(body["citations"]) >= 1
    for citation in body["citations"]:
        assert citation["document_id"] == document["id"]

