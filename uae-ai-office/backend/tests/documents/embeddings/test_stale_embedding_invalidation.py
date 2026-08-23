"""If a document is reprocessed and its chunks change, old embeddings
must not remain silently usable -- explicitly required by the Step 10
spec's lifecycle review. Step 9's reprocessing already deletes the old
chunk rows entirely (replace_document_chunks does DELETE+INSERT, not
UPDATE) before inserting the new set, so any embedding columns on those
rows are physically gone with them; the piece this step adds is
resetting documents.indexing_status back to 'not_indexed' whenever that
replacement happens (repository.mark_document_processed), so the
document doesn't keep claiming to be "indexed" for chunk content that
no longer exists.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import set_company_context
from app.modules.documents.models import Document, DocumentChunk
from tests.documents.embeddings.helpers import search, upload_process_and_index
from tests.documents.helpers import auth_header, signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes, upload_and_get_document


def _chunks_for(db_session: Session, *, company_id: uuid.UUID, document_id: uuid.UUID) -> list[DocumentChunk]:
    set_company_context(db_session, company_id)
    return list(
        db_session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        ).scalars()
    )


def test_reprocessing_an_indexed_document_resets_indexing_status(
    client: TestClient, db_session: Session
) -> None:
    token, claims = signup(client, "stale-embed-reset-status@example.com")
    company_id = uuid.UUID(claims["company_id"])
    pdf_bytes = build_native_text_pdf_bytes(["Concrete foundation specification original content."])
    document = upload_process_and_index(client, token, filename="doc.pdf", content=pdf_bytes)
    document_id = uuid.UUID(document["id"])

    set_company_context(db_session, company_id)
    indexed_row = db_session.execute(select(Document).where(Document.id == document_id)).scalar_one()
    assert indexed_row.indexing_status == "indexed"

    # reprocess (Step 9's endpoint supports safe reprocessing of an
    # already-processed document) -- replaces the chunk set even with
    # identical content, since Step 9 always deletes+reinserts.
    reprocess_response = client.post(
        f"/v1/documents/{document['id']}/process", headers=auth_header(token)
    )
    assert reprocess_response.status_code == 200

    set_company_context(db_session, company_id)
    reprocessed_row = db_session.execute(
        select(Document).where(Document.id == document_id)
    ).scalar_one()
    assert reprocessed_row.indexing_status == "not_indexed"
    assert reprocessed_row.indexed_at is None


def test_reprocessing_an_indexed_document_leaves_new_chunks_unembedded(
    client: TestClient, db_session: Session
) -> None:
    token, claims = signup(client, "stale-embed-new-chunks-unembedded@example.com")
    company_id = uuid.UUID(claims["company_id"])
    pdf_bytes = build_native_text_pdf_bytes(["Concrete foundation specification original content."])
    document = upload_process_and_index(client, token, filename="doc.pdf", content=pdf_bytes)
    document_id = uuid.UUID(document["id"])

    old_chunk_ids = {c.id for c in _chunks_for(db_session, company_id=company_id, document_id=document_id)}
    assert all(
        c.embedding is not None
        for c in _chunks_for(db_session, company_id=company_id, document_id=document_id)
    )

    client.post(f"/v1/documents/{document['id']}/process", headers=auth_header(token))

    new_chunks = _chunks_for(db_session, company_id=company_id, document_id=document_id)
    new_chunk_ids = {c.id for c in new_chunks}
    # the chunk rows themselves are brand new (old rows were deleted, not
    # updated) -- this is what physically carries the old embeddings away.
    assert old_chunk_ids.isdisjoint(new_chunk_ids)
    assert all(c.embedding is None for c in new_chunks)
    assert all(c.embedding_model is None for c in new_chunks)


def test_reprocessed_document_disappears_from_search_until_reindexed(
    client: TestClient, db_session: Session
) -> None:
    token, _ = signup(client, "stale-embed-search-disappears@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Concrete foundation specification unique wording."])
    document = upload_process_and_index(client, token, filename="doc.pdf", content=pdf_bytes)

    before = search(client, token, query="concrete foundation specification unique wording")
    assert len(before.json()["items"]) >= 1

    client.post(f"/v1/documents/{document['id']}/process", headers=auth_header(token))

    after_reprocess = search(client, token, query="concrete foundation specification unique wording")
    assert after_reprocess.json()["items"] == []

    reindex_response = client.post(
        f"/v1/documents/{document['id']}/index", headers=auth_header(token)
    )
    assert reindex_response.status_code == 200

    after_reindex = search(client, token, query="concrete foundation specification unique wording")
    assert len(after_reindex.json()["items"]) >= 1


def test_reprocessing_a_never_indexed_document_stays_not_indexed(client: TestClient) -> None:
    """Sanity check: the reset behavior doesn't accidentally *set*
    indexing_status to something wrong for a document that was never
    indexed in the first place.
    """
    token, _ = signup(client, "stale-embed-never-indexed@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Some content."])
    document = upload_and_get_document(client, token, filename="doc.pdf", content=pdf_bytes)

    client.post(f"/v1/documents/{document['id']}/process", headers=auth_header(token))
    response = client.post(f"/v1/documents/{document['id']}/process", headers=auth_header(token))

    assert response.status_code == 200
    assert response.json()["indexing_status"] == "not_indexed"

