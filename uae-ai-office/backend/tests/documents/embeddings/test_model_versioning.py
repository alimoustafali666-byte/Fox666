import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import set_company_context
from app.modules.documents.models import DocumentChunk
from tests.documents.embeddings.helpers import search, upload_process_and_index
from tests.documents.helpers import signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes

_PDF_BYTES = build_native_text_pdf_bytes(["Concrete foundation reinforcement specification content."])


# 42. same model produces compatible re-index
def test_reindexing_with_the_same_model_keeps_embedding_model_consistent(
    client: TestClient, db_session: Session
) -> None:
    token, claims = signup(client, "model-version-same@example.com")
    company_id = uuid.UUID(claims["company_id"])
    document = upload_process_and_index(client, token, filename="doc.pdf", content=_PDF_BYTES)
    document_id = uuid.UUID(document["id"])

    set_company_context(db_session, company_id)
    before_models = {
        c.embedding_model
        for c in db_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        ).scalars()
    }

    client.post(
        f"/v1/documents/{document['id']}/index", headers={"Authorization": f"Bearer {token}"}
    )

    set_company_context(db_session, company_id)
    after_models = {
        c.embedding_model
        for c in db_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        ).scalars()
    }
    assert before_models == after_models
    assert len(after_models) == 1  # every chunk agrees on one model

    # still fully searchable after re-indexing with the same model
    response = search(client, token, query="concrete foundation reinforcement specification")
    assert response.status_code == 200
    assert len(response.json()["items"]) >= 1


# 43. incompatible configured model/dimension handled explicitly
def test_chunks_embedded_by_a_different_model_are_excluded_from_search(
    client: TestClient, db_session: Session
) -> None:
    """Simulates a chunk left over from a previous embedding model: same
    dimension (so it's a structurally valid vector(1024) value -- the
    genuinely *incompatible* dimension case is already rejected outright
    by Postgres itself, see tests/db/test_pgvector_isolation.py), but a
    different embedding_model string. It must never be silently mixed
    into search results just because it happens to fit the column.
    """
    token, claims = signup(client, "model-version-different@example.com")
    company_id = uuid.UUID(claims["company_id"])
    document = upload_process_and_index(client, token, filename="doc.pdf", content=_PDF_BYTES)
    document_id = uuid.UUID(document["id"])

    set_company_context(db_session, company_id)
    chunk = db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == document_id)
    ).scalars().first()
    chunk.embedding_model = "some-retired-embedding-model-v0"
    db_session.flush()

    response = search(client, token, query="concrete foundation reinforcement specification")

    assert response.status_code == 200
    assert response.json()["items"] == []

