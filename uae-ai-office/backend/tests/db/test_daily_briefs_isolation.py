"""Raw-SQL RLS/FK proof for Step 12's two new tables -- exercises the
database policies directly, independent of application-layer filtering.
Unlike Step 11's conversations, daily_briefs/brief_items are plain
COMPANY-scoped (not creator-private): a brief is a shared artifact every
role in the company may view.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.db.session import set_company_context
from tests.db.conftest import TwoTenantSeed


def _insert_brief(db_session: Session, *, company_id, generated_by, brief_date="2026-08-21"):
    return db_session.execute(
        text(
            "INSERT INTO daily_briefs (company_id, generated_by, brief_date, summary) "
            "VALUES (:company_id, :generated_by, :brief_date, 'summary text') RETURNING id"
        ),
        {"company_id": company_id, "generated_by": generated_by, "brief_date": brief_date},
    ).scalar_one()


def _insert_brief_item(db_session: Session, *, company_id, brief_id, source_document_id=None):
    return db_session.execute(
        text(
            "INSERT INTO brief_items (company_id, brief_id, category, text, source_document_id) "
            "VALUES (:company_id, :brief_id, 'new_information', 'item text', :source_document_id) "
            "RETURNING id"
        ),
        {"company_id": company_id, "brief_id": brief_id, "source_document_id": source_document_id},
    ).scalar_one()


# 1. daily_briefs/brief_items migrations work -- proven by every test in
# this file and by tests/db/test_migrations.py's EXPECTED_TABLES round trip.


# 2. RLS isolates daily_briefs by company
def test_company_a_cannot_read_company_b_briefs(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    _insert_brief(db_session, company_id=two_tenants.company_a, generated_by=two_tenants.user_a)

    set_company_context(db_session, two_tenants.company_b)
    _insert_brief(db_session, company_id=two_tenants.company_b, generated_by=two_tenants.user_b)

    set_company_context(db_session, two_tenants.company_a)
    rows = db_session.execute(text("SELECT company_id FROM daily_briefs")).all()
    assert {r[0] for r in rows} == {two_tenants.company_a}


def test_missing_company_context_fails_closed_for_briefs(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    _insert_brief(db_session, company_id=two_tenants.company_a, generated_by=two_tenants.user_a)

    set_company_context(db_session, None)
    assert db_session.execute(text("SELECT id FROM daily_briefs")).all() == []


def test_duplicate_brief_date_within_company_is_rejected(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    _insert_brief(db_session, company_id=two_tenants.company_a, generated_by=two_tenants.user_a)

    with pytest.raises(IntegrityError), db_session.begin_nested():
        _insert_brief(db_session, company_id=two_tenants.company_a, generated_by=two_tenants.user_a)


def test_same_brief_date_allowed_across_different_companies(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    _insert_brief(db_session, company_id=two_tenants.company_a, generated_by=two_tenants.user_a)

    set_company_context(db_session, two_tenants.company_b)
    _insert_brief(db_session, company_id=two_tenants.company_b, generated_by=two_tenants.user_b)

    rows = db_session.execute(text("SELECT id FROM daily_briefs")).all()
    assert len(rows) == 1  # only company_b visible under company_b's context


# 3. RLS isolates brief_items by company
def test_company_a_cannot_read_company_b_brief_items(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    brief_a = _insert_brief(db_session, company_id=two_tenants.company_a, generated_by=two_tenants.user_a)
    _insert_brief_item(db_session, company_id=two_tenants.company_a, brief_id=brief_a)

    set_company_context(db_session, two_tenants.company_b)
    brief_b = _insert_brief(db_session, company_id=two_tenants.company_b, generated_by=two_tenants.user_b)
    _insert_brief_item(db_session, company_id=two_tenants.company_b, brief_id=brief_b)

    set_company_context(db_session, two_tenants.company_a)
    rows = db_session.execute(text("SELECT company_id FROM brief_items")).all()
    assert {r[0] for r in rows} == {two_tenants.company_a}


def test_missing_company_context_fails_closed_for_brief_items(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    brief_a = _insert_brief(db_session, company_id=two_tenants.company_a, generated_by=two_tenants.user_a)
    _insert_brief_item(db_session, company_id=two_tenants.company_a, brief_id=brief_a)

    set_company_context(db_session, None)
    assert db_session.execute(text("SELECT id FROM brief_items")).all() == []


# 4. cross-company brief/item association rejected (composite FK)
def test_brief_item_cannot_reference_another_companys_brief(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    brief_a = _insert_brief(db_session, company_id=two_tenants.company_a, generated_by=two_tenants.user_a)

    with pytest.raises((IntegrityError, DBAPIError)), db_session.begin_nested():
        db_session.execute(
            text(
                "INSERT INTO brief_items (company_id, brief_id, category, text) "
                "VALUES (:company_id, :brief_id, 'new_information', 'evil')"
            ),
            {"company_id": two_tenants.company_b, "brief_id": brief_a},
        )


def test_brief_item_cannot_reference_another_companys_document(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    brief_a = _insert_brief(db_session, company_id=two_tenants.company_a, generated_by=two_tenants.user_a)

    with pytest.raises(IntegrityError), db_session.begin_nested():
        _insert_brief_item(
            db_session, company_id=two_tenants.company_a, brief_id=brief_a,
            source_document_id=two_tenants.document_b,
        )


def test_brief_item_source_document_id_null_is_allowed(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    brief_a = _insert_brief(db_session, company_id=two_tenants.company_a, generated_by=two_tenants.user_a)
    item_id = _insert_brief_item(
        db_session, company_id=two_tenants.company_a, brief_id=brief_a, source_document_id=None
    )
    assert item_id is not None

