import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import set_company_context
from tests.db.conftest import TwoTenantSeed


def _insert_chunk(db_session: Session, *, company_id, document_id, chunk_index: int = 0):
    return db_session.execute(
        text(
            "INSERT INTO document_chunks "
            "(company_id, document_id, chunk_index, content, content_hash) "
            "VALUES (:company_id, :document_id, :chunk_index, 'chunk text', 'hash') "
            "RETURNING id"
        ),
        {"company_id": company_id, "document_id": document_id, "chunk_index": chunk_index},
    ).scalar_one()


# 1. document_chunks migration works (implicitly proven by every test in
# this file succeeding at all -- the table, RLS, and constraints below
# only exist because the migration ran cleanly)


# 2. RLS isolates chunks by company
def test_company_a_cannot_read_company_b_chunks(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    _insert_chunk(db_session, company_id=two_tenants.company_a, document_id=two_tenants.document_a)

    set_company_context(db_session, two_tenants.company_b)
    _insert_chunk(db_session, company_id=two_tenants.company_b, document_id=two_tenants.document_b)

    set_company_context(db_session, two_tenants.company_a)
    rows = db_session.execute(text("SELECT company_id FROM document_chunks")).all()

    assert {r[0] for r in rows} == {two_tenants.company_a}


def test_missing_company_context_fails_closed_for_chunks(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    _insert_chunk(db_session, company_id=two_tenants.company_a, document_id=two_tenants.document_a)

    set_company_context(db_session, None)

    assert db_session.execute(text("SELECT id FROM document_chunks")).all() == []


# 3. cross-company document/chunk association rejected
def test_chunk_cannot_reference_another_companys_document(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    """The composite FK on document_chunks(document_id, company_id) ->
    documents(id, company_id) must reject a chunk that claims to belong
    to company A while pointing at a document owned by company B --
    even with company A's own RLS context active, i.e. RLS alone would
    not have caught this.
    """
    set_company_context(db_session, two_tenants.company_a)

    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(
            text(
                "INSERT INTO document_chunks "
                "(company_id, document_id, chunk_index, content, content_hash) "
                "VALUES (:company_id, :document_id, 0, 'evil', 'hash')"
            ),
            {"company_id": two_tenants.company_a, "document_id": two_tenants.document_b},
        )


def test_chunk_unique_document_id_chunk_index(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    _insert_chunk(db_session, company_id=two_tenants.company_a, document_id=two_tenants.document_a, chunk_index=0)

    with pytest.raises(IntegrityError), db_session.begin_nested():
        _insert_chunk(
            db_session, company_id=two_tenants.company_a, document_id=two_tenants.document_a, chunk_index=0
        )

