from collections.abc import Iterator
from uuid import UUID

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, SessionTransaction, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# Keys into Session.info (a plain dict SQLAlchemy attaches to every
# Session instance and keeps for that instance's whole lifetime,
# surviving commit()/rollback() -- unlike SET LOCAL, which is scoped to
# a single Postgres transaction and is silently cleared the moment that
# transaction ends). Storing the *current* RLS context here, and
# reapplying it at the start of every subsequent transaction on the same
# Session (see _reapply_rls_context below), is what makes the context
# durable across an entire request even when orchestrator code commits
# more than once -- see set_company_context/set_user_context.
_COMPANY_CONTEXT_INFO_KEY = "rls_company_id"
_USER_CONTEXT_INFO_KEY = "rls_user_id"
_LISTENER_REGISTERED_INFO_KEY = "_rls_context_listener_registered"


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        # Explicit, not relied-upon-implicitly: SET LOCAL context (company
        # and user) lives in the Postgres transaction, and rollback() ends
        # it before the connection goes back to the pool for a future,
        # unrelated request to reuse. A prior commit() makes this a no-op
        # (nothing pending to undo); it exists specifically to guarantee
        # that a read-only request which never explicitly committed still
        # can't leave tenant context dangling on a pooled connection.
        #
        # This is still correct with the reapply-on-begin mechanism below:
        # rollback() ends the transaction without starting a new one, and
        # close() discards this Session (and its Session.info, and the
        # after_begin listener registered on it) entirely -- there is
        # nothing left that could reapply anything to the connection once
        # it goes back to the pool. The *next* request gets a brand new
        # Session with empty Session.info, so it starts from "no context"
        # regardless of what the previous request last had set.
        db.rollback()
        db.close()


def _reapply_rls_context(session: Session, transaction: SessionTransaction, connection: Connection) -> None:
    """`after_begin` fires every time this specific Session starts a new
    transaction -- including one that begins automatically after a
    mid-request db.commit()/db.rollback(), which is exactly the case
    SET LOCAL alone does not survive (it lives in the transaction that
    was just ended, not in the session or the underlying connection).

    Reads back whatever was last passed to set_company_context/
    set_user_context on THIS session and reissues it as SET LOCAL against
    the connection this new transaction just started on. A context that
    was never set (fresh session, e.g. an unauthenticated request) is
    simply absent from session.info, so this is a no-op and RLS's
    fail-closed default (no context -> zero rows) is unaffected.
    """
    if _COMPANY_CONTEXT_INFO_KEY in session.info:
        connection.execute(
            text("SELECT set_config('app.current_company_id', :value, true)"),
            {"value": session.info[_COMPANY_CONTEXT_INFO_KEY]},
        )
    if _USER_CONTEXT_INFO_KEY in session.info:
        connection.execute(
            text("SELECT set_config('app.current_user_id', :value, true)"),
            {"value": session.info[_USER_CONTEXT_INFO_KEY]},
        )


def _ensure_rls_context_survives_commits(db: Session) -> None:
    """Registers _reapply_rls_context on this Session instance exactly
    once. Instance-level (event.listen(db, ...), not the Session class or
    sessionmaker) on purpose: the listener -- and the Session.info it
    reads -- both live and die with this one request-scoped Session, so a
    later request's fresh Session (even one that reuses the same pooled
    connection) starts with neither and reapplies nothing. See
    get_db()'s docstring note and
    tests/tenancy/test_rls_transaction_safety.py for the property this
    depends on.
    """
    if db.info.get(_LISTENER_REGISTERED_INFO_KEY):
        return
    event.listen(db, "after_begin", _reapply_rls_context)
    db.info[_LISTENER_REGISTERED_INFO_KEY] = True


def set_company_context(db: Session, company_id: UUID | None) -> None:
    """Set the Postgres session variable that every RLS policy checks.

    Applied immediately (SET LOCAL, scoped to the currently open
    transaction) AND remembered on the session so it is automatically
    reapplied at the start of every later transaction this same session
    begins -- see _reapply_rls_context. A caller never needs to call this
    again after a db.commit()/db.rollback() just to keep RLS enforced;
    it only needs calling again to actually *change* the active company
    (or to explicitly clear it with None, which is remembered and
    reapplied identically -- an explicit clear stays cleared).

    Passing None clears the context, which RLS treats as "no company" ->
    zero rows, not an error -- the fail-closed behavior tenant isolation
    depends on.
    """
    value = str(company_id) if company_id is not None else ""
    db.info[_COMPANY_CONTEXT_INFO_KEY] = value
    _ensure_rls_context_survives_commits(db)
    db.execute(text("SELECT set_config('app.current_company_id', :value, true)"), {"value": value})


def set_user_context(db: Session, user_id: UUID | None) -> None:
    """Set the session variable behind two things: company_members' own
    self-lookup RLS policy (a user may always see their OWN membership
    rows, independent of any company context -- what makes it possible
    to discover "which companies am I a member of" during login/signup,
    before an active company has been chosen), and the creator-private
    RLS policy on conversations/messages/message_citations (Step 11),
    which requires BOTH app.current_company_id and app.current_user_id
    to match. Every other tenant-owned table (projects, documents,
    daily_briefs, audit_logs, ...) is unaffected by this variable.

    Same durability behavior as set_company_context: applied immediately
    and remembered on the session for automatic reapplication after any
    later commit/rollback on it.
    """
    value = str(user_id) if user_id is not None else ""
    db.info[_USER_CONTEXT_INFO_KEY] = value
    _ensure_rls_context_survives_commits(db)
    db.execute(text("SELECT set_config('app.current_user_id', :value, true)"), {"value": value})

