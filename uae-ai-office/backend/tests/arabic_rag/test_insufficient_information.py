"""Requirement 5 (Step 14): insufficient-information cases in Arabic.

Full corpus uploaded (including filler_arabic, a genuinely off-topic
Arabic document, so retrieval has something semantically nearby to
correctly reject, not just an empty corpus -- mirrors the English
evaluation dataset's F_insufficient category and its terms_filler
fixture) -- then Arabic questions about facts that appear in NONE of the
uploaded documents. The correct, safe outcome is a refusal, not a
fabricated figure borrowed from an unrelated document.
"""

from fastapi.testclient import TestClient

from app.core.llm.fake_provider import FakeLLMProvider
from tests.arabic_rag.fixtures import all_fixtures
from tests.arabic_rag.helpers import upload_corpus
from tests.conversations.helpers import ask, create_conversation
from tests.documents.helpers import signup


def _setup_corpus(client: TestClient, email: str) -> str:
    token, _ = signup(client, email)
    upload_corpus(client, token, all_fixtures())
    return token


def _ask(client: TestClient, token: str, question: str):
    conversation = create_conversation(client, token)
    return ask(client, token, conversation_id=conversation["id"], question=question)


def test_arabic_question_with_no_grounding_is_refused(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token = _setup_corpus(client, "insufficient-profit@example.com")

    response = _ask(client, token, "ما هو صافي ربح الشركة في عام 2025؟")  # company's 2025 net profit

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is False
    assert body["citations"] == []
    # No fabricated figure from ANY of the uploaded documents' amounts.
    for forbidden in ("125,000", "98,000", "210,000", "62,500", "29,408.25"):
        assert forbidden not in body["content"]


def test_arabic_question_about_unrelated_bank_details_is_refused(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token = _setup_corpus(client, "insufficient-bank@example.com")

    response = _ask(client, token, "ما هو رقم الحساب البنكي للعميل؟")  # customer's bank account number

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is False
    assert body["citations"] == []


def test_arabic_question_about_unrelated_projected_profit_is_refused(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token = _setup_corpus(client, "insufficient-projected-profit@example.com")

    response = _ask(client, token, "ما هي الأرباح المتوقعة لعام 2027؟")  # projected 2027 profit

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is False
    assert body["citations"] == []


def test_arabic_question_never_reaches_the_llm_when_retrieval_finds_nothing(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    """Insufficient information is decided by retrieval, before any LLM
    call -- confirms the fixed template response isn't itself an
    (expensive, or trust-shifting) model call."""
    token = _setup_corpus(client, "insufficient-no-llm-call@example.com")

    _ask(client, token, "ما هو صافي ربح الشركة في عام 2025؟")

    assert fake_llm_provider.calls == []

