"""Requirements 1-3 (Step 14): exact-value Arabic/bilingual RAG cases
across the four required language-pairing combinations, covering AED
amounts, quantities, percentages, dates, and reference numbers.

All five required document types are covered across this suite:
contract, quotation, purchase order, and invoice here (DOCX); BOQ/XLSX in
test_boq_source_location.py.

Every case here uploads the FULL corpus (all ten fixtures) into one
company, so a correct answer proves genuine retrieval discrimination
between multiple similar-but-distinct documents -- not just "the only
candidate available" (mirroring the English evaluation dataset's own
H_retrieval_confusion category). Full corpus + exact numbers here means
the same-document, same-language combination (AR doc -> AR question);
see test_bilingual_and_cross_lingual.py for the bilingual-document and
cross-lingual combinations, which need document-scoped retrieval for
reasons explained there.
"""

from fastapi.testclient import TestClient

from app.core.llm.fake_provider import FakeLLMProvider
from tests.arabic_rag.fixtures import all_fixtures
from tests.arabic_rag.helpers import upload_corpus
from tests.conversations.helpers import ask, create_conversation
from tests.documents.helpers import signup


def _setup_corpus(client: TestClient, email: str) -> tuple[str, dict[str, dict]]:
    token, _ = signup(client, email)
    documents = upload_corpus(client, token, all_fixtures())
    return token, documents


def _ask(client: TestClient, token: str, question: str):
    conversation = create_conversation(client, token)
    return ask(client, token, conversation_id=conversation["id"], question=question)


# --- AED amounts ---------------------------------------------------------


def test_arabic_contract_aed_amount(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, documents = _setup_corpus(client, "matrix-aed-contract@example.com")
    response = _ask(client, token, "ما قيمة هذا العقد؟")
    body = response.json()
    assert body["is_sufficient"] is True
    assert "125,000" in body["content"]
    assert "98,000" not in body["content"]
    assert "210,000" not in body["content"]
    assert body["citations"][0]["document_id"] == documents["contract_arabic"]["id"]


def test_arabic_invoice_aed_amount_and_vat(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, documents = _setup_corpus(client, "matrix-aed-invoice@example.com")
    response = _ask(client, token, "كم مبلغ هذه الفاتورة؟")
    body = response.json()
    assert body["is_sufficient"] is True
    assert "62,500" in body["content"]
    assert body["citations"][0]["document_id"] == documents["invoice_arabic"]["id"]

    vat_response = _ask(client, token, "كم ضريبة القيمة المضافة في الفاتورة؟")
    vat_body = vat_response.json()
    assert vat_body["is_sufficient"] is True
    assert "3,125" in vat_body["content"]


def test_arabic_invoice_total_due(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _documents = _setup_corpus(client, "matrix-total-due@example.com")
    response = _ask(client, token, "ما الإجمالي المستحق في الفاتورة؟")
    body = response.json()
    assert body["is_sufficient"] is True
    assert "65,625" in body["content"]


def test_arabic_po_aed_amount(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, documents = _setup_corpus(client, "matrix-aed-po@example.com")
    response = _ask(client, token, "ما قيمة أمر الشراء؟")
    body = response.json()
    assert body["is_sufficient"] is True
    assert "125,000" in body["content"]
    assert body["citations"][0]["document_id"] == documents["po_arabic"]["id"]


def test_arabic_quotation_aed_amount(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, documents = _setup_corpus(client, "matrix-aed-quotation@example.com")
    response = _ask(client, token, "كم إجمالي مبلغ عرض السعر؟")
    body = response.json()
    assert body["is_sufficient"] is True
    assert "125,000" in body["content"]
    assert body["citations"][0]["document_id"] == documents["quotation_arabic"]["id"]


# --- Percentages -----------------------------------------------------------


def test_arabic_retention_percentage(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, documents = _setup_corpus(client, "matrix-percentage@example.com")
    response = _ask(client, token, "ما نسبة الضمان في هذا العقد؟")
    body = response.json()
    assert body["is_sufficient"] is True
    assert "5%" in body["content"]
    assert body["citations"][0]["document_id"] == documents["contract_arabic"]["id"]


# --- Dates -------------------------------------------------------------


def test_arabic_contract_signing_date(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _documents = _setup_corpus(client, "matrix-date@example.com")
    response = _ask(client, token, "ما تاريخ توقيع هذا العقد؟")
    body = response.json()
    assert body["is_sufficient"] is True
    assert "2026-01-15" in body["content"]


# --- Reference numbers / item descriptions --------------------------------


def test_arabic_quotation_reference_number(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, documents = _setup_corpus(client, "matrix-refnum-quotation@example.com")
    response = _ask(client, token, "ما رقم عرض السعر؟")
    body = response.json()
    assert body["is_sufficient"] is True
    assert "QT-2026-0777" in body["content"]
    assert body["citations"][0]["document_id"] == documents["quotation_arabic"]["id"]


def test_arabic_po_reference_number(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, documents = _setup_corpus(client, "matrix-refnum-po@example.com")
    response = _ask(client, token, "ما رقم أمر الشراء؟")
    body = response.json()
    assert body["is_sufficient"] is True
    assert "PO-2026-0654" in body["content"]
    assert body["citations"][0]["document_id"] == documents["po_arabic"]["id"]


def test_arabic_invoice_reference_number(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, documents = _setup_corpus(client, "matrix-refnum-invoice@example.com")
    response = _ask(client, token, "ما رقم الفاتورة؟")
    body = response.json()
    assert body["is_sufficient"] is True
    assert "INV-2026-0888" in body["content"]
    assert body["citations"][0]["document_id"] == documents["invoice_arabic"]["id"]


def test_arabic_payment_terms_item_description(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    """Payment-terms wording is a free-text "item description" style fact
    (not a bare number), exercised end to end."""
    token, documents = _setup_corpus(client, "matrix-terms@example.com")
    response = _ask(client, token, "ما شروط دفع هذا العقد؟")
    body = response.json()
    assert body["is_sufficient"] is True
    assert "30" in body["content"]
    assert body["citations"][0]["document_id"] == documents["contract_arabic"]["id"]

