import pytest
from sqlalchemy import text
from sqlalchemy.exc import DataError
from sqlalchemy.orm import Session

from app.db.session import set_company_context
from app.modules.documents.models import EMBEDDING_VECTOR_DIMENSION
from tests.db.conftest import TwoTenantSeed


def _vector_literal(*, dimension: int, hot_index: int) -> str:
    """A unit vector with a 1 at `hot_index` and 0 elsewhere, as a
    pgvector text literal -- e.g. '[1,0,0]'.
    """
    values = [0] * dimension
    values[hot_index] = 1
    return "[" + ",".join(str(v) for v in values) + "]"


def _insert_chunk_with_embedding(
    db_session: Session, *, company_id, document_id, hot_index: int, chunk_index: int = 0
):
    vector = _vector_literal(dimension=EMBEDDING_VECTOR_DIMENSION, hot_index=hot_index)
    return db_session.execute(
        text(
            "INSERT INTO document_chunks "
            "(company_id, document_id, chunk_index, content, content_hash, embedding, embedding_model) "
            "VALUES (:company_id, :document_id, :chunk_index, 'chunk text', 'hash', "
            f"CAST(:vector AS vector({EMBEDDING_VECTOR_DIMENSION})), 'test-model') "
            "RETURNING id"
        ),
        {
            "company_id": company_id,
            "document_id": document_id,
            "chunk_index": chunk_index,
            "vector": vector,
        },
    ).scalar_one()


# 2. embedding dimension enforced correctly (DB level)
def test_inserting_a_wrong_dimension_vector_fails_clearly(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    wrong_dimension_vector = "[1,0,0]"  # 3 dims, column is vector(1024)

    with pytest.raises(DataError), db_session.begin_nested():
        db_session.execute(
            text(
                "INSERT INTO document_chunks "
                "(company_id, document_id, chunk_index, content, content_hash, embedding) "
                "VALUES (:company_id, :document_id, 0, 'x', 'hash', CAST(:vector AS vector(1024)))"
            ),
            {
                "company_id": two_tenants.company_a,
                "document_id": two_tenants.document_a,
                "vector": wrong_dimension_vector,
            },
        )


# 24. RLS independently scopes vector search
def test_rls_alone_blocks_cross_company_vector_search(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    """No application-layer company_id filter here at all -- proves RLS
    by itself (FORCE ROW LEVEL SECURITY on document_chunks) is
    sufficient to keep a cosine-similarity query scoped to one company,
    regardless of how similar another company's vector is.
    """
    set_company_context(db_session, two_tenants.company_a)
    _insert_chunk_with_embedding(
        db_session, company_id=two_tenants.company_a, document_id=two_tenants.document_a, hot_index=0
    )

    set_company_context(db_session, two_tenants.company_b)
    # identical vector direction as company A's chunk -- if RLS were not
    # enforced, this would be a perfect (distance 0) match for A's query.
    _insert_chunk_with_embedding(
        db_session, company_id=two_tenants.company_b, document_id=two_tenants.document_b, hot_index=0
    )

    set_company_context(db_session, two_tenants.company_a)
    query_vector = _vector_literal(dimension=EMBEDDING_VECTOR_DIMENSION, hot_index=0)
    rows = db_session.execute(
        text(
            "SELECT company_id FROM document_chunks "
            "ORDER BY embedding <=> CAST(:qv AS vector(1024)) LIMIT 10"
        ),
        {"qv": query_vector},
    ).all()

    assert {r[0] for r in rows} == {two_tenants.company_a}


def test_missing_company_context_returns_no_vector_search_results(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    _insert_chunk_with_embedding(
        db_session, company_id=two_tenants.company_a, document_id=two_tenants.document_a, hot_index=0
    )

    set_company_context(db_session, None)
    query_vector = _vector_literal(dimension=EMBEDDING_VECTOR_DIMENSION, hot_index=0)
    rows = db_session.execute(
        text(
            "SELECT company_id FROM document_chunks "
            "ORDER BY embedding <=> CAST(:qv AS vector(1024)) LIMIT 10"
        ),
        {"qv": query_vector},
    ).all()

    assert rows == []

