"""Proves two, deliberately distinct, properties of RLS context:

1. It cannot survive a connection being returned to the pool and checked
   out again for a later, unrelated request (a fresh Session starts with
   empty Session.info, so nothing is reapplied) -- the property the
   whole tenant-isolation design depends on when connections are reused
   under load.
2. Within the SAME Session, it DOES survive a mid-request commit/rollback
   (app.db.session's after_begin listener reapplies it from Session.info
   at the start of every new transaction that Session begins), while an
   explicit clear (set_company_context(session, None)) still sticks. See
   test_tenant_context_survives_a_mid_session_commit_but_an_explicit_clear_still_sticks
   for the regression this guards: document processing/indexing, Ask
   Your Business, and any other orchestrator with more than one
   db.commit() per request used to silently lose RLS context after the
   first commit.

Deliberately does NOT use the shared db_session/client fixtures from
conftest.py: those intentionally hold one open transaction for an entire
test (so app-level commit() calls don't escape it), which is the right
tool for testing business logic but would prove nothing here -- there
would only ever be one transaction, never a real checkin/checkout cycle,
and (before the fix) a real commit's context loss couldn't reproduce at
all under that fixture.
"""

import os
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.db.session import set_company_context, set_user_context

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://uae_app:uae_app@localhost:5432/uae_ai_office_test",
)


def _current_company_setting(session: Session) -> str | None:
    return session.execute(
        text("SELECT current_setting('app.current_company_id', true)")
    ).scalar_one()


def _current_user_setting(session: Session) -> str | None:
    return session.execute(
        text("SELECT current_setting('app.current_user_id', true)")
    ).scalar_one()


def _end_request_like_get_db_does(session: Session) -> None:
    """Mirrors app.db.session.get_db()'s finally block exactly: rollback
    before close, so this test proves the same mechanism the real
    request-handling path relies on, not a different one.
    """
    session.rollback()
    session.close()


def test_pooled_connection_does_not_leak_company_context_between_requests() -> None:
    # pool_size=1, max_overflow=0: only one underlying connection can ever
    # exist, so two sequential (non-overlapping) sessions are GUARANTEED
    # to reuse the exact same one -- proving the checkin/checkout cycle
    # itself clears SET LOCAL state, not just that "a" connection happened
    # to be fresh.
    engine = create_engine(TEST_DATABASE_URL, pool_size=1, max_overflow=0)
    try:
        company_a = uuid.uuid4()

        request_one = Session(bind=engine)
        set_company_context(request_one, company_a)
        assert _current_company_setting(request_one) == str(company_a)
        _end_request_like_get_db_does(request_one)

        request_two = Session(bind=engine)
        leaked = _current_company_setting(request_two)
        _end_request_like_get_db_does(request_two)

        assert leaked in (None, ""), (
            f"company context leaked across pooled connection reuse: {leaked!r}"
        )
    finally:
        engine.dispose()


def test_pooled_connection_does_not_leak_user_context_between_requests() -> None:
    engine = create_engine(TEST_DATABASE_URL, pool_size=1, max_overflow=0)
    try:
        user_a = uuid.uuid4()

        request_one = Session(bind=engine)
        set_user_context(request_one, user_a)
        assert _current_user_setting(request_one) == str(user_a)
        _end_request_like_get_db_does(request_one)

        request_two = Session(bind=engine)
        leaked = _current_user_setting(request_two)
        _end_request_like_get_db_does(request_two)

        assert leaked in (None, ""), (
            f"user context leaked across pooled connection reuse: {leaked!r}"
        )
    finally:
        engine.dispose()


def test_second_tenant_does_not_inherit_first_tenants_context_on_reused_connection() -> None:
    """The exact scenario named in the brief: "a request for Company A
    followed by Company B using a reused connection must not inherit
    Company A context" -- proven directly rather than inferred from the
    two single-value tests above.
    """
    engine = create_engine(TEST_DATABASE_URL, pool_size=1, max_overflow=0)
    try:
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()

        request_for_a = Session(bind=engine)
        set_company_context(request_for_a, company_a)
        assert _current_company_setting(request_for_a) == str(company_a)
        _end_request_like_get_db_does(request_for_a)

        request_for_b = Session(bind=engine)
        set_company_context(request_for_b, company_b)
        seen = _current_company_setting(request_for_b)
        _end_request_like_get_db_does(request_for_b)

        assert seen == str(company_b), "company B's request must see only company B's context"
    finally:
        engine.dispose()


def test_tenant_context_survives_a_mid_session_commit_but_an_explicit_clear_still_sticks() -> None:
    """SET LOCAL itself is transaction-scoped -- a bare rollback/commit
    ends the transaction it was set in and Postgres discards it, exactly
    like the two pool-reuse tests above rely on for a *fresh* Session.
    But set_company_context/set_user_context also remember the value on
    the Session itself (Session.info) and reapply it via an `after_begin`
    listener the instant this SAME Session starts its next transaction --
    see app.db.session._reapply_rls_context. That's the fix for the bug
    where document processing/indexing, Ask Your Business, and any other
    orchestrator that calls db.commit() more than once per request would
    silently lose RLS context after the first commit and have every
    later write in that request rejected by RLS ("new row violates row-
    level security policy"), invisibly outside this test suite because
    the shared db_session fixture's join_transaction_mode="create_savepoint"
    never actually ends the real transaction between "commits".

    So: a mid-session rollback/commit with NO explicit reset must not
    silently drop the tenant context (that's the whole fix) -- but an
    explicit set_company_context(session, None) must still clear it, and
    that clear must itself survive a later rollback/commit the same way,
    preserving the fail-closed default.
    """
    engine = create_engine(TEST_DATABASE_URL)
    try:
        session = Session(bind=engine)
        company_a = uuid.uuid4()

        set_company_context(session, company_a)
        assert _current_company_setting(session) == str(company_a)

        session.rollback()

        # The transaction that carried the SET LOCAL is gone, but the next
        # statement autobegins a new one and after_begin reapplies it --
        # this is the fix, proven directly against real SET LOCAL/rollback
        # semantics, not the savepoint-joined fixture.
        assert _current_company_setting(session) == str(company_a)

        set_company_context(session, None)
        session.rollback()

        after_explicit_clear = _current_company_setting(session)
        assert after_explicit_clear in (None, ""), (
            "an explicit clear must stay cleared across a later rollback, "
            "not be silently resurrected"
        )

        session.rollback()
        session.close()
    finally:
        engine.dispose()


def test_missing_tenant_context_on_a_fresh_connection_fails_closed() -> None:
    """A brand-new connection that never called set_company_context at
    all -- not just one that had it cleared -- must also see no rows on
    a tenant-owned table, reinforcing the fail-closed default.

    Deliberately creates and commits a real, known row first (rather than
    just asserting the table happens to be empty): this proves "a row
    that verifiably exists is still invisible with no context", which
    holds regardless of whatever else is in the shared dev database, and
    cleans up after itself since this file bypasses the rollback-based
    fixtures on purpose.
    """
    engine = create_engine(TEST_DATABASE_URL)
    try:
        setup_session = Session(bind=engine)
        company_id = setup_session.execute(
            text("INSERT INTO companies (name) VALUES ('RLS Fail-Closed Probe') RETURNING id")
        ).scalar_one()
        user_id = setup_session.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES ('rls-fail-closed-probe@example.com', 'x') RETURNING id"
            )
        ).scalar_one()
        set_company_context(setup_session, company_id)
        setup_session.execute(
            text(
                "INSERT INTO company_members (company_id, user_id, role) "
                "VALUES (:company_id, :user_id, 'owner')"
            ),
            {"company_id": company_id, "user_id": user_id},
        )
        setup_session.commit()
        setup_session.close()

        try:
            fresh_session = Session(bind=engine)
            rows = fresh_session.execute(
                text("SELECT id FROM company_members WHERE company_id = :company_id"),
                {"company_id": company_id},
            ).all()
            fresh_session.rollback()
            fresh_session.close()

            assert rows == [], "a row known to exist must still be invisible with no company context"
        finally:
            cleanup_session = Session(bind=engine)
            set_company_context(cleanup_session, company_id)
            cleanup_session.execute(
                text("DELETE FROM company_members WHERE company_id = :company_id"),
                {"company_id": company_id},
            )
            set_company_context(cleanup_session, None)
            # Deleting a company (or a user) checks, via FKs from every
            # append-only table (audit_logs -- migration 0009; task_comments
            # and task_activity -- migration 0018), whether any row there
            # references it, and Postgres implements that check as a
            # locking SELECT ... FOR KEY SHARE against each such table --
            # which requires UPDATE privilege, revoked from uae_app by
            # each of those migrations' append-only enforcement. As the
            # tables' owner, uae_app can always re-grant this to itself
            # (see migration 0009's docstring on why this is only an
            # accident-guard, not a hard boundary); test cleanup is
            # exactly the kind of administrative script allowed to do so,
            # unlike normal request-handling application code. Both
            # deletes below need the grant, so it's lifted only after
            # both are done.
            cleanup_session.execute(text("GRANT UPDATE, DELETE ON audit_logs, task_comments, task_activity TO uae_app"))
            cleanup_session.execute(
                text("DELETE FROM companies WHERE id = :company_id"), {"company_id": company_id}
            )
            cleanup_session.execute(
                text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id}
            )
            cleanup_session.execute(text("REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs, task_comments, task_activity FROM uae_app"))
            cleanup_session.commit()
            cleanup_session.close()
    finally:
        engine.dispose()

