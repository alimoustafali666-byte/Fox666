"""Migration 0009 revokes UPDATE/DELETE/TRUNCATE on audit_logs from the
app role at the database level. Deliberately uses its own raw engine/
connection rather than the rollback-savepoint db_session fixture: a
permission error aborts the current Postgres transaction outright (it
cannot be "tried and caught" mid-savepoint the way a constraint
violation can inside that fixture's join_transaction_mode), so each
check here gets a clean connection of its own.
"""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://uae_app:uae_app@localhost:5432/uae_ai_office_test",
)


def _with_fresh_session(fn) -> None:
    engine = create_engine(TEST_DATABASE_URL)
    try:
        session = Session(bind=engine)
        try:
            fn(session)
        finally:
            session.rollback()
            session.close()
    finally:
        engine.dispose()


# 20. normal application path cannot update an audit record
def test_normal_app_role_cannot_update_audit_logs() -> None:
    def attempt(session: Session) -> None:
        try:
            session.execute(text("UPDATE audit_logs SET action = 'tampered' WHERE true"))
            raised = False
        except ProgrammingError:
            raised = True
        assert raised, "UPDATE on audit_logs must be rejected at the database level"

    _with_fresh_session(attempt)


# 21. normal application path cannot delete an audit record
def test_normal_app_role_cannot_delete_audit_logs() -> None:
    def attempt(session: Session) -> None:
        try:
            session.execute(text("DELETE FROM audit_logs WHERE true"))
            raised = False
        except ProgrammingError:
            raised = True
        assert raised, "DELETE on audit_logs must be rejected at the database level"

    _with_fresh_session(attempt)


def test_normal_app_role_cannot_truncate_audit_logs() -> None:
    def attempt(session: Session) -> None:
        try:
            session.execute(text("TRUNCATE audit_logs"))
            raised = False
        except ProgrammingError:
            raised = True
        assert raised, "TRUNCATE on audit_logs must be rejected at the database level"

    _with_fresh_session(attempt)


def test_normal_app_role_can_still_insert_audit_logs() -> None:
    """The point of append-only is INSERT-only, not no-access."""

    def attempt(session: Session) -> None:
        company_id = session.execute(
            text("INSERT INTO companies (name) VALUES ('Append Only Co') RETURNING id")
        ).scalar_one()
        session.execute(
            text("SELECT set_config('app.current_company_id', :cid, true)"),
            {"cid": str(company_id)},
        )
        session.execute(
            text(
                "INSERT INTO audit_logs (company_id, action, resource_type) "
                "VALUES (:company_id, 'system.probe', 'system')"
            ),
            {"company_id": company_id},
        )
        # rolled back by the caller, never committed -- no cleanup needed

    _with_fresh_session(attempt)

