import hashlib
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import set_company_context
from app.modules.documents.models import DocumentChunk
from tests.documents.helpers import signup
from tests.documents.processing.helpers import (
    build_boq_xlsx_bytes,
    build_native_text_pdf_bytes,
    trigger_processing,
    upload_and_get_document,
)


def _chunks_for(db_session: Session, *, company_id: uuid.UUID, document_id: uuid.UUID) -> list[DocumentChunk]:
    set_company_context(db_session, company_id)
    return list(
        db_session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        ).scalars()
    )


# 23. content_hash is correct
def test_content_hash_matches_sha256_of_chunk_content(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "chunk-hash@example.com")
    document = upload_and_get_document(
        client, token, filename="doc.pdf", content=build_native_text_pdf_bytes(["Some content here."])
    )
    trigger_processing(client, token, document["id"])

    chunks = _chunks_for(
        db_session, company_id=uuid.UUID(claims["company_id"]), document_id=uuid.UUID(document["id"])
    )
    assert chunks
    for chunk in chunks:
        assert chunk.content_hash == hashlib.sha256(chunk.content.encode()).hexdigest()


# 24. source location stored
def test_source_location_stored_for_pdf_pages(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "chunk-source-pdf@example.com")
    document = upload_and_get_document(
        client, token, filename="doc.pdf",
        content=build_native_text_pdf_bytes(["Page one content.", "Page two content."]),
    )
    trigger_processing(client, token, document["id"])

    chunks = _chunks_for(
        db_session, company_id=uuid.UUID(claims["company_id"]), document_id=uuid.UUID(document["id"])
    )
    assert all(c.page_number is not None for c in chunks)
    assert all(c.source_location and "pages" in c.source_location for c in chunks)


def test_source_location_stored_for_xlsx_sheet_and_rows(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "chunk-source-xlsx@example.com")
    document = upload_and_get_document(
        client, token, filename="boq.xlsx", content=build_boq_xlsx_bytes()
    )
    trigger_processing(client, token, document["id"])

    chunks = _chunks_for(
        db_session, company_id=uuid.UUID(claims["company_id"]), document_id=uuid.UUID(document["id"])
    )
    assert all(c.sheet_name == "BOQ" for c in chunks)
    assert all(c.source_location and c.source_location.get("sheet_name") == "BOQ" for c in chunks)
    assert all("rows" in c.source_location for c in chunks)


def test_chunk_index_is_sequential_and_zero_based(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "chunk-index@example.com")
    document = upload_and_get_document(
        client, token, filename="doc.pdf",
        content=build_native_text_pdf_bytes(["Page one.", "Page two.", "Page three."]),
    )
    trigger_processing(client, token, document["id"])

    chunks = _chunks_for(
        db_session, company_id=uuid.UUID(claims["company_id"]), document_id=uuid.UUID(document["id"])
    )
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))

