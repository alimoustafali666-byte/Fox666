"""Shared plumbing for the Arabic RAG pipeline-validation suite: uploading
the synthetic corpus and reading back persisted chunk rows directly, so
tests can assert on exactly what was stored, not just what the API
echoes back.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.documents.models import DocumentChunk
from tests.arabic_rag.fixtures import ArabicDocumentFixture
from tests.documents.embeddings.helpers import upload_process_and_index


def upload_fixture(client: TestClient, token: str, fixture: ArabicDocumentFixture) -> dict:
    return upload_process_and_index(
        client, token,
        filename=fixture.filename, content=fixture.content, document_type=fixture.document_type,
    )


def upload_corpus(
    client: TestClient, token: str, fixtures: list[ArabicDocumentFixture]
) -> dict[str, dict]:
    """Uploads, processes, and indexes every given fixture, returning
    {fixture_key: document_json}. All documents land in one company/
    corpus so retrieval must actually discriminate between them, not
    just return the only candidate available.
    """
    return {fixture.key: upload_fixture(client, token, fixture) for fixture in fixtures}


def chunks_for_document(db_session: Session, document_id: str) -> list[DocumentChunk]:
    return list(
        db_session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == uuid.UUID(document_id))
            .order_by(DocumentChunk.chunk_index)
        ).scalars()
    )


def all_chunk_content(db_session: Session, document_id: str) -> str:
    """Every chunk's content concatenated, for a simple "does this exact
    text appear anywhere in what was actually persisted" check.
    """
    return "\n".join(chunk.content for chunk in chunks_for_document(db_session, document_id))

