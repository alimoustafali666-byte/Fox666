"""Requirement 8 (Step 14): Arabic/Unicode text must survive
upload -> parsing -> normalization -> chunking -> retrieval -> response
without corruption, reversal, or number changes.

Every check here reads back what was ACTUALLY PERSISTED (the DocumentChunk
row in Postgres) and compares it byte-for-byte (after NFC normalization,
the one normalization the pipeline itself deliberately performs -- see
app.modules.documents.processing.normalize) against the exact Arabic text
the fixture was authored with. This is pipeline correctness, not model
quality: FakeEmbeddingProvider/FakeLLMProvider do no real translation or
reasoning (see their module docstrings), so a correct retrieval/response
here proves the plumbing preserves and correctly threads Arabic content
through every stage -- it says nothing about what a real Voyage/Claude
model would retrieve or say, which remains unverified (see the Step 14
report).
"""

import unicodedata

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.llm.fake_provider import FakeLLMProvider
from tests.arabic_rag.fixtures import contract_arabic
from tests.arabic_rag.helpers import all_chunk_content, chunks_for_document, upload_fixture
from tests.conversations.helpers import ask, create_conversation
from tests.documents.helpers import signup


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


# Exact substrings the source document was authored with -- any mojibake,
# character reversal, or digit corruption would make one of these fail.
EXPECTED_EXACT_SUBSTRINGS = [
    "رقم العقد: CTR-2026-0501",
    "المشروع الخاضع لهذا العقد: تجديد فيلا الخوانيج",
    "قيمة هذا العقد: AED 125,000 (مائة وخمسة وعشرون ألف درهم إماراتي).",
    "شروط دفع هذا العقد: 30 يوماً صافي من تاريخ الفاتورة.",
    "نسبة الضمان في هذا العقد: 5% من قيمة العقد.",
    "تاريخ توقيع هذا العقد: 2026-01-15 الموافق 15 يناير 2026.",
]


def test_arabic_document_survives_upload_parse_normalize_chunk_byte_exact(
    client: TestClient, db_session: Session, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "arabic-integrity@example.com")
    document = upload_fixture(client, token, contract_arabic())

    persisted = all_chunk_content(db_session, document["id"])

    for expected in EXPECTED_EXACT_SUBSTRINGS:
        assert _nfc(expected) in _nfc(persisted), (
            f"Expected exact Arabic substring not found after upload/parse/normalize/chunk: {expected!r}"
        )


def test_arabic_chunk_content_is_not_byte_reversed(client: TestClient, db_session: Session) -> None:
    """A naive byte-level mishandling of RTL text (e.g. treating it as a
    fixed left-to-right byte string and reversing it) would turn
    "العقد" into something else entirely -- assert the real word, in its
    real (logical, not visual) character order, is present.
    """
    token, _ = signup(client, "arabic-reversal@example.com")
    document = upload_fixture(client, token, contract_arabic())

    persisted = all_chunk_content(db_session, document["id"])

    assert "العقد" in persisted
    assert "دقعلا" not in persisted  # "العقد" reversed character-by-character


def test_arabic_numbers_and_currency_are_not_altered(client: TestClient, db_session: Session) -> None:
    """AED amounts, percentages, and dates embedded in Arabic prose must
    come through with their exact digits -- no locale-driven digit
    substitution (Western <-> Eastern Arabic-Indic numerals), no
    thousands-separator mangling, no off-by-one date corruption.
    """
    token, _ = signup(client, "arabic-numbers@example.com")
    document = upload_fixture(client, token, contract_arabic())

    persisted = all_chunk_content(db_session, document["id"])

    assert "125,000" in persisted
    assert "5%" in persisted
    assert "2026-01-15" in persisted
    # Never silently transliterated to Eastern Arabic-Indic digits (would
    # indicate some normalization step touched digit characters, which
    # normalize_text's own docstring promises never happens).
    assert "١٢٥" not in persisted  # Eastern Arabic-Indic "125"


def test_arabic_query_retrieves_and_response_preserves_arabic_text_end_to_end(
    client: TestClient, db_session: Session, fake_llm_provider: FakeLLMProvider
) -> None:
    """Full round trip: Arabic query -> FakeEmbeddingProvider ranks the
    Arabic chunk correctly (proving the Unicode-tokenizer fix works, see
    app.core.embeddings.fake_provider) -> FakeLLMProvider's default
    word-overlap grounding selects and echoes it -> the HTTP JSON response
    contains the exact Arabic answer text, unmangled by serialization.
    """
    token, _ = signup(client, "arabic-roundtrip@example.com")
    upload_fixture(client, token, contract_arabic())
    conversation = create_conversation(client, token)

    response = ask(client, token, conversation_id=conversation["id"], question="ما قيمة هذا العقد؟")

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is True
    assert "125,000" in body["content"]
    assert "العقد" in body["content"]
    assert len(body["citations"]) >= 1


def test_arabic_chunk_content_matches_cited_chunk_row_exactly(
    client: TestClient, db_session: Session, fake_llm_provider: FakeLLMProvider
) -> None:
    """The chunk the API cites must be byte-identical to what's actually
    stored -- proves the response path doesn't re-derive or reformat
    Arabic text anywhere between storage and the citation the client sees.
    """
    token, _ = signup(client, "arabic-citation-exact@example.com")
    document = upload_fixture(client, token, contract_arabic())
    conversation = create_conversation(client, token)

    response = ask(client, token, conversation_id=conversation["id"], question="ما قيمة هذا العقد؟")
    body = response.json()
    cited_chunk_id = body["citations"][0]["document_chunk_id"]

    stored_chunks = {str(c.id): c.content for c in chunks_for_document(db_session, document["id"])}
    assert cited_chunk_id in stored_chunks
    # The default FakeLLMProvider grounding echoes the cited chunk's
    # content verbatim as the answer (see its module docstring) -- so the
    # response content and the stored chunk content must match exactly.
    assert body["content"].strip() == stored_chunks[cited_chunk_id].strip()

