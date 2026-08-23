from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import set_company_context
from tests.db.conftest import TwoTenantSeed


def test_company_a_cannot_read_company_b_projects(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)

    rows = db_session.execute(text("SELECT id FROM projects")).all()

    assert {r[0] for r in rows} == {two_tenants.project_a}


def test_company_a_cannot_read_company_b_documents(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)

    rows = db_session.execute(text("SELECT id FROM documents")).all()

    assert {r[0] for r in rows} == {two_tenants.document_a}


def test_company_a_cannot_read_company_b_audit_logs(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)

    rows = db_session.execute(
        text("SELECT company_id FROM audit_logs")
    ).all()

    assert {r[0] for r in rows} == {two_tenants.company_a}


def test_company_a_cannot_read_company_b_members(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)

    rows = db_session.execute(text("SELECT company_id FROM company_members")).all()

    assert {r[0] for r in rows} == {two_tenants.company_a}


def test_missing_company_context_fails_closed(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    """No SET LOCAL at all -- current_setting(..., true) returns NULL, and
    the RLS policy must treat that as zero rows, not an error and not "see
    everything".
    """
    projects = db_session.execute(text("SELECT id FROM projects")).all()
    documents = db_session.execute(text("SELECT id FROM documents")).all()
    audit_logs = db_session.execute(text("SELECT id FROM audit_logs")).all()

    assert projects == []
    assert documents == []
    assert audit_logs == []


def test_explicitly_cleared_company_context_fails_closed(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    assert db_session.execute(text("SELECT id FROM projects")).all() != []

    set_company_context(db_session, None)

    assert db_session.execute(text("SELECT id FROM projects")).all() == []


def test_company_b_sees_only_its_own_rows(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_b)

    rows = db_session.execute(text("SELECT id FROM projects")).all()

    assert {r[0] for r in rows} == {two_tenants.project_b}

