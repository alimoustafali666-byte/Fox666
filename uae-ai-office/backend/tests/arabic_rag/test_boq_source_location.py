"""Requirement 4 (Step 14): Arabic BOQ/XLSX retrieval cases with
sheet/row source verification.

Two fixtures, two different things proven:

- boq_arabic (four line items, one chunk): direct chunk/DB inspection --
  sheet_name and the source_location row range are correct, and every
  item's exact Arabic description, quantity, and rate survive parsing/
  chunking byte-for-byte. Does not depend on retrieval similarity scoring
  at all.
- boq_arabic_focused (one line item): the full upload -> process -> index
  -> ask() -> citation round trip, proving sheet/row source location
  also survives all the way out through the API's citation payload, not
  just in the database.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.llm.fake_provider import FakeLLMProvider
from tests.arabic_rag.fixtures import boq_arabic, boq_arabic_focused
from tests.arabic_rag.helpers import chunks_for_document, upload_fixture
from tests.conversations.helpers import ask, create_conversation
from tests.documents.helpers import signup


def test_arabic_boq_sheet_name_and_row_range_are_correct(
    client: TestClient, db_session: Session
) -> None:
    token, _ = signup(client, "boq-sheet-row@example.com")
    document = upload_fixture(client, token, boq_arabic())

    chunks = chunks_for_document(db_session, document["id"])
    assert len(chunks) >= 1
    chunk = chunks[0]

    assert chunk.sheet_name == "جدول الكميات"
    assert chunk.source_location is not None
    assert chunk.source_location["sheet_name"] == "جدول الكميات"
    # Header is row 1 (not a data element); four data rows span rows 2-5.
    assert chunk.source_location["rows"] == [2, 5]


def test_arabic_boq_item_descriptions_and_quantities_survive_exactly(
    client: TestClient, db_session: Session
) -> None:
    token, _ = signup(client, "boq-values@example.com")
    document = upload_fixture(client, token, boq_arabic())

    chunks = chunks_for_document(db_session, document["id"])
    content = "\n".join(c.content for c in chunks)

    # Arabic item descriptions, exact.
    assert "توريد وتركيب خرسانة درجة 30" in content
    assert "توريد وتركيب خرسانة درجة 40" in content
    assert "حديد تسليح درجة 60" in content
    assert "أعمال الشدة الخشبية للسقف المعلق" in content

    # Exact quantities/units/rates/amounts, no rounding or truncation.
    assert "20" in content and "m3" in content and "300" in content and "6000" in content
    assert "50" in content and "350" in content and "17500" in content
    assert "10.5" in content and "ton" in content and "2800.75" in content and "29408.25" in content
    assert "120" in content and "m2" in content and "45" in content and "5400" in content


def test_arabic_boq_retrieval_and_citation_source_location_end_to_end(
    client: TestClient, db_session: Session, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "boq-e2e@example.com")
    document = upload_fixture(client, token, boq_arabic_focused())
    conversation = create_conversation(client, token)

    response = ask(
        client, token, conversation_id=conversation["id"],
        document_id=document["id"], question="ما كمية حديد تسليح درجة 60 في جدول الكميات؟",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["is_sufficient"] is True
    assert "10.5" in body["content"]
    assert "حديد تسليح درجة 60" in body["content"]

    citation = body["citations"][0]
    assert citation["document_id"] == document["id"]

    cited_chunk = next(
        c for c in chunks_for_document(db_session, document["id"]) if str(c.id) == citation["document_chunk_id"]
    )
    assert cited_chunk.sheet_name == "جدول الكميات"
    assert cited_chunk.source_location["sheet_name"] == "جدول الكميات"
    assert cited_chunk.source_location["rows"] == [2, 2]

