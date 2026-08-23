"""Requirement 7 (Step 14): citation validation and exact source-location
checks for Arabic content, beyond what test_boq_source_location.py
already covers for XLSX. Confirms that a citation the API returns is
never fabricated (points at a real, persisted chunk of the real,
expected document) and that the source-location metadata that chunk
carries (section_name for DOCX; see test_boq_source_location.py for
XLSX sheet/row) is exactly what the parser recorded, for Arabic
document/section names.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.llm.fake_provider import FakeLLMProvider
from tests.arabic_rag.fixtures import contract_arabic, invoice_arabic
from tests.arabic_rag.helpers import chunks_for_document, upload_fixture
from tests.conversations.helpers import ask, create_conversation
from tests.documents.helpers import signup


def test_arabic_citation_points_at_a_real_persisted_chunk_of_the_expected_document(
    client: TestClient, db_session: Session, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "citation-real-chunk@example.com")
    document = upload_fixture(client, token, contract_arabic())
    conversation = create_conversation(client, token)

    response = ask(client, token, conversation_id=conversation["id"], question="ما قيمة هذا العقد؟")

    assert response.status_code == 201
    body = response.json()
    assert len(body["citations"]) >= 1

    real_chunk_ids = {str(c.id) for c in chunks_for_document(db_session, document["id"])}
    for citation in body["citations"]:
        assert citation["document_id"] == document["id"]
        assert citation["document_chunk_id"] in real_chunk_ids


def test_arabic_citation_section_name_matches_the_arabic_heading(
    client: TestClient, db_session: Session, fake_llm_provider: FakeLLMProvider
) -> None:
    """docx_parser.py records the Arabic heading text itself as
    section_name (app.modules.documents.processing.docx_parser) -- the
    cited chunk's section_name must be the real Arabic heading, not a
    transliteration, translation, or corrupted form of it.
    """
    token, _ = signup(client, "citation-section-name@example.com")
    document = upload_fixture(client, token, contract_arabic())
    conversation = create_conversation(client, token)

    response = ask(client, token, conversation_id=conversation["id"], question="ما قيمة هذا العقد؟")
    body = response.json()
    citation = body["citations"][0]

    cited_chunk = next(
        c for c in chunks_for_document(db_session, document["id"]) if str(c.id) == citation["document_chunk_id"]
    )
    assert cited_chunk.section_name == "عقد مقاولة"


def test_arabic_invoice_citation_points_at_the_correct_document_not_a_sibling(
    client: TestClient, db_session: Session, fake_llm_provider: FakeLLMProvider
) -> None:
    """A second document (contract_arabic) is present in the same
    corpus -- proves the citation resolves to the INVOICE specifically,
    not just to "some document"."""
    token, _ = signup(client, "citation-not-sibling@example.com")
    contract_document = upload_fixture(client, token, contract_arabic())
    invoice_document = upload_fixture(client, token, invoice_arabic())
    conversation = create_conversation(client, token)

    response = ask(client, token, conversation_id=conversation["id"], question="كم مبلغ هذه الفاتورة؟")

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is True
    assert len(body["citations"]) >= 1
    for citation in body["citations"]:
        assert citation["document_id"] == invoice_document["id"]
        assert citation["document_id"] != contract_document["id"]


def test_arabic_citation_chunk_content_hash_is_stable(
    client: TestClient, db_session: Session, fake_llm_provider: FakeLLMProvider
) -> None:
    """content_hash is computed once at processing time and never
    touched again -- confirms the cited chunk's stored content still
    hashes to its own recorded content_hash, i.e. nothing re-wrote or
    re-encoded the Arabic content between processing and citation."""
    import hashlib

    token, _ = signup(client, "citation-content-hash@example.com")
    document = upload_fixture(client, token, contract_arabic())
    conversation = create_conversation(client, token)

    response = ask(client, token, conversation_id=conversation["id"], question="ما قيمة هذا العقد؟")
    body = response.json()
    citation = body["citations"][0]

    cited_chunk = next(
        c for c in chunks_for_document(db_session, document["id"]) if str(c.id) == citation["document_chunk_id"]
    )
    assert cited_chunk.content_hash == hashlib.sha256(cited_chunk.content.encode("utf-8")).hexdigest()

