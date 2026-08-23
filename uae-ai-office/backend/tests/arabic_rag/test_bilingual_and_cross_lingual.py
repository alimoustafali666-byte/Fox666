"""Requirement 2 (Step 14), the remaining three language-pairing
combinations: bilingual document -> Arabic and English questions, and
the two true cross-lingual combinations (Arabic document -> English
question, English document -> Arabic question).

All cases here scope retrieval to one specific document via the ask()
`document_id` parameter, for two different reasons documented per case
below -- never because scoping is needed to get a PASS; see each
docstring for what the scoping is actually proving.
"""

from fastapi.testclient import TestClient

from app.core.llm.fake_provider import FakeLLMProvider
from tests.arabic_rag.fixtures import (
    contract_arabic,
    contract_bilingual,
    contract_english,
    po_arabic,
)
from tests.arabic_rag.helpers import upload_fixture
from tests.conversations.helpers import ask, create_conversation
from tests.documents.helpers import signup


def _ask_scoped(client: TestClient, token: str, *, document_id: str, question: str):
    conversation = create_conversation(client, token)
    return ask(client, token, conversation_id=conversation["id"], document_id=document_id, question=question)


# --- Bilingual document -> Arabic and English questions --------------------
#
# document_id scoping here is NOT what makes these pass -- it isolates the
# measurement. contract_arabic and contract_bilingual both legitimately
# contain the words "العقد"/"contract" repeated many times; without
# scoping, a corpus-wide bag-of-words ranking would non-deterministically
# favor whichever sibling document happens to repeat the matching
# language's terms more densely (measured while building this suite --
# see the Step 14 report). Scoping to the specific bilingual document is
# exactly what "ask about THIS document" (the API's own document_id
# filter) is for, and still applies the real similarity threshold -- nothing
# here bypasses retrieval scoring.


def test_bilingual_document_arabic_question(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _ = signup(client, "bilingual-ar@example.com")
    document = upload_fixture(client, token, contract_bilingual())

    response = _ask_scoped(client, token, document_id=document["id"], question="ما قيمة هذا العقد؟")

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is True
    assert "210,000" in body["content"]
    assert body["citations"][0]["document_id"] == document["id"]


def test_bilingual_document_english_question(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _ = signup(client, "bilingual-en@example.com")
    document = upload_fixture(client, token, contract_bilingual())

    response = _ask_scoped(client, token, document_id=document["id"], question="What is the contract value?")

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is True
    assert "210,000" in body["content"]
    assert body["citations"][0]["document_id"] == document["id"]


def test_bilingual_document_arabic_question_retention(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "bilingual-ar-retention@example.com")
    document = upload_fixture(client, token, contract_bilingual())

    response = _ask_scoped(client, token, document_id=document["id"], question="ما نسبة الضمان في هذا العقد؟")

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is True
    assert "7%" in body["content"]


def test_bilingual_document_english_question_payment_terms(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "bilingual-en-terms@example.com")
    document = upload_fixture(client, token, contract_bilingual())

    response = _ask_scoped(
        client, token, document_id=document["id"], question="What are the payment terms of this contract?"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is True
    assert "60" in body["content"]


# --- True cross-lingual: Arabic document -> English question, and back ---
#
# See tests/arabic_rag/fixtures.py's module docstring and the Step 14
# report for the full disclosure. FakeEmbeddingProvider is a literal bag-
# of-words hash with no translation or semantic capability at all -- an
# English question sharing no literal tokens with an Arabic-only document
# (or vice versa) never clears the retrieval similarity threshold under
# this provider, MEASURED, not assumed, including with bare reference-
# number queries. document_id scoping is used here specifically to prove
# this is a genuine "no semantically-relevant content found" outcome for
# THIS document, not an artifact of a wrong document being searched.
#
# The property under test is real and worth having regardless: a
# provider with no cross-lingual understanding must fail SAFELY --
# returning "insufficient information" -- rather than fabricating an
# answer or leaking unrelated document content across the language
# boundary. Whether a real multilingual embedding model (Voyage) succeeds
# where this fake provider structurally cannot is unverified here and
# remains a pre-production, live-provider requirement.


def test_arabic_document_english_question_fails_safe_not_fabricated(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "cross-lingual-ar-doc-en-q@example.com")
    document = upload_fixture(client, token, contract_arabic())

    response = _ask_scoped(
        client, token, document_id=document["id"], question="What is the contract value?"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is False
    assert body["citations"] == []
    # No leaked Arabic document content, and no fabricated English or
    # Arabic figure -- the templated insufficient-information response,
    # nothing else.
    assert "125,000" not in body["content"]
    assert fake_llm_provider.calls == []  # never even reached the LLM: retrieval found nothing


def test_english_document_arabic_question_fails_safe_not_fabricated(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "cross-lingual-en-doc-ar-q@example.com")
    document = upload_fixture(client, token, contract_english())

    response = _ask_scoped(client, token, document_id=document["id"], question="ما قيمة العقد؟")

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is False
    assert body["citations"] == []
    assert "98,000" not in body["content"]
    assert fake_llm_provider.calls == []


def test_arabic_po_document_english_question_fails_safe(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    """Second Arabic-document/English-question pair (a purchase order,
    not a contract), so this isn't a single-fixture coincidence."""
    token, _ = signup(client, "cross-lingual-po@example.com")
    document = upload_fixture(client, token, po_arabic())

    response = _ask_scoped(
        client, token, document_id=document["id"], question="What is the purchase order value?"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is False
    assert body["citations"] == []

