"""Evaluation-only retrieval query: same shape as
app.modules.documents.retrieval_service.search(), but deliberately
WITHOUT the similarity-threshold filter, so the harness can measure
Recall@k against the true ranking (independent of whatever threshold is
currently configured) and separately record, per candidate, whether the
CURRENTLY configured threshold would have kept or dropped it -- the
distinction the "THRESHOLD CALIBRATION" and "retrieval failure vs
generation failure" sections of the Step 11.5 spec require.

Not part of app/ (production business logic) on purpose -- this is
eval/diagnostic tooling only, never imported by the request-serving path.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.documents.models import Document, DocumentChunk


def raw_ranked_candidates(
    db: Session,
    *,
    company_id: uuid.UUID,
    query_vector: list[float],
    embedding_model: str,
    limit: int = 20,
    document_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    document_type: str | None = None,
) -> list[tuple[DocumentChunk, float]]:
    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    score = 1 - distance

    stmt = (
        select(DocumentChunk, score.label("score"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.company_id == company_id,
            DocumentChunk.embedding.is_not(None),
            DocumentChunk.embedding_model == embedding_model,
            Document.deleted_at.is_(None),
        )
    )
    if document_id is not None:
        stmt = stmt.where(DocumentChunk.document_id == document_id)
    if project_id is not None:
        stmt = stmt.where(Document.project_id == project_id)
    if document_type is not None:
        stmt = stmt.where(Document.document_type == document_type)

    stmt = stmt.order_by(distance.asc()).limit(limit)
    rows = db.execute(stmt).all()
    return [(chunk, float(row_score)) for chunk, row_score in rows]

