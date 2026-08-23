import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.embeddings.exceptions import EmbeddingOperationError, EmbeddingUnavailable
from app.core.embeddings.factory import get_embedding_provider
from app.db.session import set_company_context
from app.modules.documents.models import Document, DocumentChunk
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.helpers import auth_header, seed_member, signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes, upload_and_get_document

_PDF_BYTES = build_native_text_pdf_bytes(["Real extractable content for indexing tests."])


def _chunks_for(db_session: Session, *, company_id: uuid.UUID, document_id: uuid.UUID) -> list[DocumentChunk]:
    set_company_context(db_session, company_id)
    return list(
        db_session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        ).scalars()
    )


# 7. processed document can be indexed
def test_processed_document_can_be_indexed(client: TestClient) -> None:
    token, _ = signup(client, "index-processed@example.com")
    document = upload_process_and_index(client, token, filename="doc.pdf", content=_PDF_BYTES)

    assert document["indexing_status"] == "indexed"


# 8. unprocessed document cannot be indexed
def test_unprocessed_document_cannot_be_indexed(client: TestClient) -> None:
    token, _ = signup(client, "index-unprocessed@example.com")
    document = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)

    response = client.post(f"/v1/documents/{document['id']}/index", headers=auth_header(token))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "document_not_processed"


# 9. deleted document cannot be indexed
def test_deleted_document_cannot_be_indexed(client: TestClient) -> None:
    token, _ = signup(client, "index-deleted@example.com")
    document = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)
    client.post(f"/v1/documents/{document['id']}/process", headers=auth_header(token))
    client.delete(f"/v1/documents/{document['id']}", headers=auth_header(token))

    response = client.post(f"/v1/documents/{document['id']}/index", headers=auth_header(token))

    assert response.status_code == 404


# 10. owner can index
def test_owner_can_index(client: TestClient) -> None:
    token, _ = signup(client, "index-rbac-owner@example.com")
    document = upload_process_and_index(client, token, filename="doc.pdf", content=_PDF_BYTES)
    assert document["indexing_status"] == "indexed"


# 11. admin can index
def test_admin_can_index(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "index-rbac-admin-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    doc = upload_and_get_document(client, owner_token, filename="doc.pdf", content=_PDF_BYTES)
    client.post(f"/v1/documents/{doc['id']}/process", headers=auth_header(owner_token))
    admin_token = seed_member(db_session, company_id=company_id, email="index-rbac-admin@example.com", role="admin")

    response = client.post(f"/v1/documents/{doc['id']}/index", headers=auth_header(admin_token))

    assert response.status_code == 200, response.text


# 12. manager can index
def test_manager_can_index(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "index-rbac-manager-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    doc = upload_and_get_document(client, owner_token, filename="doc.pdf", content=_PDF_BYTES)
    client.post(f"/v1/documents/{doc['id']}/process", headers=auth_header(owner_token))
    manager_token = seed_member(
        db_session, company_id=company_id, email="index-rbac-manager@example.com", role="manager"
    )

    response = client.post(f"/v1/documents/{doc['id']}/index", headers=auth_header(manager_token))

    assert response.status_code == 200, response.text


# 13. member cannot index
def test_member_cannot_index(client: TestClient, db_session: Session) -> None:
    owner_token, owner_claims = signup(client, "index-rbac-member-owner@example.com")
    company_id = uuid.UUID(owner_claims["company_id"])
    doc = upload_and_get_document(client, owner_token, filename="doc.pdf", content=_PDF_BYTES)
    client.post(f"/v1/documents/{doc['id']}/process", headers=auth_header(owner_token))
    member_token = seed_member(
        db_session, company_id=company_id, email="index-rbac-member@example.com", role="member"
    )

    response = client.post(f"/v1/documents/{doc['id']}/index", headers=auth_header(member_token))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


# 14. chunk vectors persist correctly
def test_chunk_vectors_persist_correctly(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "index-vectors-persist@example.com")
    document = upload_process_and_index(client, token, filename="doc.pdf", content=_PDF_BYTES)

    chunks = _chunks_for(
        db_session, company_id=uuid.UUID(claims["company_id"]), document_id=uuid.UUID(document["id"])
    )
    assert chunks
    for chunk in chunks:
        assert chunk.embedding is not None
        assert len(chunk.embedding) == get_embedding_provider().dimension


# 15. embedding model identifier persists
def test_embedding_model_identifier_persists(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "index-model-persists@example.com")
    document = upload_process_and_index(client, token, filename="doc.pdf", content=_PDF_BYTES)

    chunks = _chunks_for(
        db_session, company_id=uuid.UUID(claims["company_id"]), document_id=uuid.UUID(document["id"])
    )
    provider = get_embedding_provider()
    assert all(c.embedding_model == provider.model_identifier for c in chunks)
    assert all(c.embedded_at is not None for c in chunks)


# 16. indexing state transitions correctly
def test_indexing_state_transitions_correctly(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "index-state-transitions@example.com")
    company_id = uuid.UUID(claims["company_id"])
    doc = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)

    set_company_context(db_session, company_id)
    before = db_session.execute(select(Document).where(Document.id == uuid.UUID(doc["id"]))).scalar_one()
    assert before.indexing_status == "not_indexed"

    client.post(f"/v1/documents/{doc['id']}/process", headers=auth_header(token))
    index_response = client.post(f"/v1/documents/{doc['id']}/index", headers=auth_header(token))
    assert index_response.status_code == 200

    set_company_context(db_session, company_id)
    after = db_session.execute(select(Document).where(Document.id == uuid.UUID(doc["id"]))).scalar_one()
    assert after.indexing_status == "indexed"
    assert after.indexed_at is not None
    assert after.indexing_error_code is None


# 17. provider failure marks indexing failed safely
def test_provider_failure_marks_indexing_failed_safely(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, claims = signup(client, "index-provider-failure@example.com")
    company_id = uuid.UUID(claims["company_id"])
    doc = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)
    client.post(f"/v1/documents/{doc['id']}/process", headers=auth_header(token))

    provider = get_embedding_provider()

    def boom(texts):
        raise EmbeddingUnavailable("simulated provider outage with internal detail XYZ-999")

    monkeypatch.setattr(provider, "embed_batch", boom)

    response = client.post(f"/v1/documents/{doc['id']}/index", headers=auth_header(token))

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "indexing_unavailable"
    assert "XYZ-999" not in response.text

    set_company_context(db_session, company_id)
    row = db_session.execute(select(Document).where(Document.id == uuid.UUID(doc["id"]))).scalar_one()
    assert row.indexing_status == "failed"
    assert row.indexing_error_code == "embedding_provider_unavailable"


def _many_words_page(word_count: int, prefix: str) -> str:
    return " ".join(f"{prefix}{i}" for i in range(word_count))


# 18. provider response wrong vector count rejected (orchestrator level)
def test_orchestrator_rejects_wrong_vector_count_from_provider(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, claims = signup(client, "index-wrong-count@example.com")
    # Enough distinct pages/words that chunking is guaranteed to produce
    # more than one chunk (well over the ~650 target-token chunk size).
    multi_chunk_pdf = build_native_text_pdf_bytes(
        [_many_words_page(400, f"page{p}word") for p in range(6)]
    )
    doc = upload_and_get_document(client, token, filename="multi.pdf", content=multi_chunk_pdf)
    client.post(f"/v1/documents/{doc['id']}/process", headers=auth_header(token))

    chunk_count = len(
        _chunks_for(db_session, company_id=uuid.UUID(claims["company_id"]), document_id=uuid.UUID(doc["id"]))
    )
    assert chunk_count > 1, "test fixture must produce multiple chunks to be meaningful"

    provider = get_embedding_provider()
    monkeypatch.setattr(provider, "embed_batch", lambda texts: [[0.0] * provider.dimension])  # always 1

    response = client.post(f"/v1/documents/{doc['id']}/index", headers=auth_header(token))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "indexing_failed"


# batching / resource control: a document's chunks are embedded in
# bounded batches, never all sent to the provider in one request.
def test_indexing_embeds_chunks_in_bounded_batches(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "embedding_batch_size", 2)
    token, claims = signup(client, "index-bounded-batches@example.com")
    multi_chunk_pdf = build_native_text_pdf_bytes(
        [_many_words_page(400, f"page{p}word") for p in range(6)]
    )
    doc = upload_and_get_document(client, token, filename="multi.pdf", content=multi_chunk_pdf)
    client.post(f"/v1/documents/{doc['id']}/process", headers=auth_header(token))

    document_id = uuid.UUID(doc["id"])
    company_id = uuid.UUID(claims["company_id"])
    chunk_count = len(_chunks_for(db_session, company_id=company_id, document_id=document_id))
    assert chunk_count > 2, "test fixture must exceed the batch size to be meaningful"

    provider = get_embedding_provider()
    real_embed_batch = provider.embed_batch
    batch_sizes: list[int] = []

    def spying_embed_batch(texts):
        batch_sizes.append(len(texts))
        assert len(texts) <= 2, "batch exceeded the configured embedding_batch_size"
        return real_embed_batch(texts)

    monkeypatch.setattr(provider, "embed_batch", spying_embed_batch)

    response = client.post(f"/v1/documents/{doc['id']}/index", headers=auth_header(token))

    assert response.status_code == 200, response.text
    assert len(batch_sizes) > 1  # more than one request was made
    assert sum(batch_sizes) == chunk_count  # every chunk was embedded exactly once
    chunks = _chunks_for(db_session, company_id=company_id, document_id=document_id)
    assert all(c.embedding is not None for c in chunks)


# 19. provider response wrong dimension rejected (orchestrator level)
def test_orchestrator_rejects_wrong_dimension_from_provider(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, _ = signup(client, "index-wrong-dimension@example.com")
    doc = upload_and_get_document(client, token, filename="doc.pdf", content=_PDF_BYTES)
    client.post(f"/v1/documents/{doc['id']}/process", headers=auth_header(token))

    provider = get_embedding_provider()
    monkeypatch.setattr(provider, "embed_batch", lambda texts: [[0.0] * (provider.dimension - 1)] * len(texts))

    response = client.post(f"/v1/documents/{doc['id']}/index", headers=auth_header(token))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "indexing_failed"


# 20. re-index succeeds without duplicating embeddings
def test_reindex_succeeds_without_duplicating_embeddings(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "index-reindex-no-dup@example.com")
    company_id = uuid.UUID(claims["company_id"])
    document = upload_process_and_index(client, token, filename="doc.pdf", content=_PDF_BYTES)
    document_id = uuid.UUID(document["id"])

    first_chunks = _chunks_for(db_session, company_id=company_id, document_id=document_id)
    first_count = len(first_chunks)

    reindex_response = client.post(f"/v1/documents/{document['id']}/index", headers=auth_header(token))
    assert reindex_response.status_code == 200, reindex_response.text

    second_chunks = _chunks_for(db_session, company_id=company_id, document_id=document_id)
    assert len(second_chunks) == first_count
    assert all(c.embedding is not None for c in second_chunks)


def test_reindex_writes_reindexed_audit_action(client: TestClient, db_session: Session) -> None:
    from app.modules.audit_log.models import AuditLog

    token, claims = signup(client, "index-reindex-audit@example.com")
    company_id = uuid.UUID(claims["company_id"])
    document = upload_process_and_index(client, token, filename="doc.pdf", content=_PDF_BYTES)

    client.post(f"/v1/documents/{document['id']}/index", headers=auth_header(token))

    set_company_context(db_session, company_id)
    actions = list(
        db_session.execute(select(AuditLog.action).order_by(AuditLog.created_at.asc())).scalars()
    )
    assert actions.count("document.indexing_succeeded") == 2
    assert "document.reindexed" in actions


# 21. failed re-index preserves previous known-good vectors
def test_failed_reindex_preserves_previous_known_good_vectors(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, claims = signup(client, "index-preserve-good@example.com")
    company_id = uuid.UUID(claims["company_id"])
    document = upload_process_and_index(client, token, filename="doc.pdf", content=_PDF_BYTES)
    document_id = uuid.UUID(document["id"])

    good_chunks = _chunks_for(db_session, company_id=company_id, document_id=document_id)
    good_vectors = [list(c.embedding) for c in good_chunks]
    assert good_vectors and all(v is not None for v in good_vectors)

    provider = get_embedding_provider()

    def always_fails(texts):
        raise EmbeddingOperationError("simulated permanent provider failure")

    monkeypatch.setattr(provider, "embed_batch", always_fails)

    response = client.post(f"/v1/documents/{document['id']}/index", headers=auth_header(token))
    assert response.status_code == 422

    still_there = _chunks_for(db_session, company_id=company_id, document_id=document_id)
    still_there_vectors = [list(c.embedding) for c in still_there]
    assert still_there_vectors == good_vectors

    set_company_context(db_session, company_id)
    row = db_session.execute(select(Document).where(Document.id == document_id)).scalar_one()
    assert row.indexing_status == "failed"
    # the document itself is still considered processed/searchable via
    # its OLD embeddings -- indexing_status reflects the failed attempt,
    # but nothing destroyed the previously-successful vectors above.
    assert row.status == "processed"

