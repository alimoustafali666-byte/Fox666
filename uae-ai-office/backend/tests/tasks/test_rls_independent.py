"""RLS tested independently of application filtering: raw SQL directly
against the session, bypassing app.modules.tasks.service and
repository entirely, to prove tenant/visibility isolation is enforced by
Postgres itself (migration 0018's tenant_visibility_* policies) -- not
merely an application-layer WHERE clause a future bug could remove.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import set_company_context, set_user_context
from app.modules.auth.models import User
from app.modules.tenancy.models import Company, CompanyMember


def _make_user(db_session: Session, email: str) -> User:
    user = User(email=email, password_hash=hash_password("x"), full_name="RLS Test")
    db_session.add(user)
    db_session.flush()
    return user


def test_raw_sql_cannot_read_cross_company_task(db_session: Session) -> None:
    company_a = Company(name="Tasks Company A")
    company_b = Company(name="Tasks Company B")
    db_session.add_all([company_a, company_b])
    db_session.flush()

    alice = _make_user(db_session, "trls1a@example.com")
    eve = _make_user(db_session, "trls1e@example.com")

    set_company_context(db_session, company_a.id)
    set_user_context(db_session, alice.id)
    db_session.add(CompanyMember(company_id=company_a.id, user_id=alice.id, role="owner"))
    db_session.flush()

    task_id = uuid.uuid4()
    db_session.execute(
        text("INSERT INTO tasks (id, company_id, title, created_by) VALUES (:id, :company_id, 'secret', :created_by)"),
        {"id": task_id, "company_id": company_a.id, "created_by": alice.id},
    )

    set_company_context(db_session, company_b.id)
    set_user_context(db_session, eve.id)
    db_session.add(CompanyMember(company_id=company_b.id, user_id=eve.id, role="owner"))
    db_session.flush()

    rows = db_session.execute(text("SELECT id FROM tasks WHERE id = :id"), {"id": task_id}).fetchall()
    assert rows == []


def test_raw_sql_plain_member_cannot_read_unscoped_task_of_another_member(db_session: Session) -> None:
    company = Company(name="Same Tasks Co")
    db_session.add(company)
    db_session.flush()

    alice = _make_user(db_session, "trls2a@example.com")
    mallory = _make_user(db_session, "trls2m@example.com")

    set_company_context(db_session, company.id)
    set_user_context(db_session, alice.id)
    db_session.add_all([
        CompanyMember(company_id=company.id, user_id=alice.id, role="member"),
        CompanyMember(company_id=company.id, user_id=mallory.id, role="member"),
    ])
    db_session.flush()

    task_id = uuid.uuid4()
    db_session.execute(
        text(
            "INSERT INTO tasks (id, company_id, title, created_by, assigned_to) "
            "VALUES (:id, :company_id, 'alice personal task', :created_by, :assigned_to)"
        ),
        {"id": task_id, "company_id": company.id, "created_by": alice.id, "assigned_to": alice.id},
    )

    set_user_context(db_session, mallory.id)
    rows = db_session.execute(text("SELECT id FROM tasks WHERE id = :id"), {"id": task_id}).fetchall()
    assert rows == []

    # Mallory also cannot forge an UPDATE on it (0 rows affected, not an error).
    result = db_session.execute(text("UPDATE tasks SET status = 'completed' WHERE id = :id"), {"id": task_id})
    assert result.rowcount == 0


def test_raw_sql_management_role_can_read_unscoped_task(db_session: Session) -> None:
    company = Company(name="Mgmt Tasks Co")
    db_session.add(company)
    db_session.flush()

    alice = _make_user(db_session, "trls3a@example.com")
    boss = _make_user(db_session, "trls3b@example.com")

    set_company_context(db_session, company.id)
    set_user_context(db_session, alice.id)
    db_session.add_all([
        CompanyMember(company_id=company.id, user_id=alice.id, role="member"),
        CompanyMember(company_id=company.id, user_id=boss.id, role="manager"),
    ])
    db_session.flush()

    task_id = uuid.uuid4()
    db_session.execute(
        text("INSERT INTO tasks (id, company_id, title, created_by) VALUES (:id, :company_id, 'alice task', :created_by)"),
        {"id": task_id, "company_id": company.id, "created_by": alice.id},
    )

    set_user_context(db_session, boss.id)
    rows = db_session.execute(text("SELECT id FROM tasks WHERE id = :id"), {"id": task_id}).fetchall()
    assert len(rows) == 1


def test_raw_sql_forged_created_by_insert_rejected(db_session: Session) -> None:
    company = Company(name="Forge Tasks Co")
    db_session.add(company)
    db_session.flush()

    alice = _make_user(db_session, "trls4a@example.com")
    mallory = _make_user(db_session, "trls4m@example.com")

    set_company_context(db_session, company.id)
    set_user_context(db_session, alice.id)
    db_session.add_all([
        CompanyMember(company_id=company.id, user_id=alice.id, role="member"),
        CompanyMember(company_id=company.id, user_id=mallory.id, role="member"),
    ])
    db_session.flush()

    set_user_context(db_session, mallory.id)

    from psycopg.errors import InsufficientPrivilege
    from sqlalchemy.exc import ProgrammingError

    try:
        db_session.execute(
            text("INSERT INTO tasks (id, company_id, title, created_by) VALUES (:id, :company_id, 'forged', :created_by)"),
            {"id": uuid.uuid4(), "company_id": company.id, "created_by": alice.id},
        )
        raise AssertionError("SECURITY BUG: mallory inserted a task impersonating alice as created_by")
    except ProgrammingError as exc:
        assert isinstance(exc.orig, InsufficientPrivilege)
        db_session.rollback()

