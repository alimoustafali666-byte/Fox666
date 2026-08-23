import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.session import set_company_context
from app.modules.audit_log.models import AuditLog
from app.modules.audit_log.sanitizer import UnsafeAuditMetadataError
from app.modules.audit_log.service import InvalidAuditActionError, record_audit_event


def _make_company_and_user(db_session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    company_id = db_session.execute(
        text("INSERT INTO companies (name) VALUES ('Audit Co') RETURNING id")
    ).scalar_one()
    user_id = db_session.execute(
        text(
            "INSERT INTO users (email, password_hash) VALUES ('audit-svc@example.com', 'x') RETURNING id"
        )
    ).scalar_one()
    return company_id, user_id


# 1. centralized audit helper inserts correctly
# 2. audit event is company-scoped
# 3. actor_user_id is recorded correctly
# 4. resource_type/resource_id are recorded
def test_record_audit_event_inserts_with_all_fields(db_session: Session) -> None:
    company_id, user_id = _make_company_and_user(db_session)
    resource_id = uuid.uuid4()
    set_company_context(db_session, company_id)

    entry = record_audit_event(
        db_session,
        company_id=company_id,
        actor_user_id=user_id,
        action="project.create",
        resource_type="project",
        resource_id=resource_id,
        metadata={"name": "New Project"},
        ip_address="203.0.113.5",
    )
    db_session.flush()

    assert entry.company_id == company_id
    assert entry.actor_user_id == user_id
    assert entry.action == "project.create"
    assert entry.resource_type == "project"
    assert entry.resource_id == resource_id
    assert entry.metadata_ == {"name": "New Project"}
    assert entry.ip_address == "203.0.113.5"

    fetched = db_session.execute(
        select(AuditLog).where(AuditLog.id == entry.id)
    ).scalar_one()
    assert fetched.company_id == company_id


def test_record_audit_event_allows_no_actor_and_no_resource(db_session: Session) -> None:
    company_id, _ = _make_company_and_user(db_session)
    set_company_context(db_session, company_id)

    entry = record_audit_event(
        db_session,
        company_id=company_id,
        action="system.something_happened",
        resource_type="system",
    )

    assert entry.actor_user_id is None
    assert entry.resource_id is None
    assert entry.metadata_ is None


@pytest.mark.parametrize(
    "action",
    [
        "signup",  # missing namespace
        "Auth.Signup",  # wrong case
        "auth..signup",  # empty segment
        "auth.sign up",  # space
        ".signup",
        "auth.",
        "123.abc",  # must start with a letter
    ],
)
def test_record_audit_event_rejects_malformed_action_names(
    db_session: Session, action: str
) -> None:
    company_id, _ = _make_company_and_user(db_session)
    set_company_context(db_session, company_id)

    with pytest.raises(InvalidAuditActionError):
        record_audit_event(db_session, company_id=company_id, action=action, resource_type="x")


@pytest.mark.parametrize(
    "action",
    [
        "auth.signup",
        "project.create",
        "document.download",
        "membership.role_change",
    ],
)
def test_record_audit_event_accepts_well_formed_action_names(
    db_session: Session, action: str
) -> None:
    company_id, _ = _make_company_and_user(db_session)
    set_company_context(db_session, company_id)

    entry = record_audit_event(db_session, company_id=company_id, action=action, resource_type="x")

    assert entry.action == action


def test_record_audit_event_propagates_sanitizer_rejection(db_session: Session) -> None:
    """record_audit_event does not swallow a sanitizer violation -- it's
    the caller's job to decide what that means for their transaction
    (see app.modules.auth.service for the two different policies).
    """
    company_id, _ = _make_company_and_user(db_session)
    set_company_context(db_session, company_id)

    with pytest.raises(UnsafeAuditMetadataError):
        record_audit_event(
            db_session,
            company_id=company_id,
            action="auth.login_failure",
            resource_type="user",
            metadata={"password": "should-never-be-here"},
        )


def test_ip_address_round_trips_as_a_plain_string_not_an_ipaddress_object(
    db_session: Session,
) -> None:
    """Regression test: psycopg3's default adapter for a Postgres INET
    column returns ipaddress.IPv4Address/IPv6Address on SELECT, not str,
    which the AuditLogEntry Pydantic schema (typed `ip_address: str |
    None`) rejected outright -- GET /v1/audit-logs 500'd on any row with
    a non-null ip_address. The model's `ip_address` column now uses
    InetAddress (app.modules.audit_log.models), a TypeDecorator that
    converts back to str on read. Checking the attribute immediately
    after record_audit_event() returns proves nothing (it's still the
    Python string that was assigned, never round-tripped) -- db_session
    is forced to expire and reload the row from Postgres so
    InetAddress.process_result_value actually runs.
    """
    company_id, _ = _make_company_and_user(db_session)
    set_company_context(db_session, company_id)

    entry = record_audit_event(
        db_session, company_id=company_id, action="project.create",
        resource_type="project", ip_address="203.0.113.5",
    )
    db_session.flush()
    db_session.expire(entry)

    reloaded = db_session.execute(select(AuditLog).where(AuditLog.id == entry.id)).scalar_one()

    assert reloaded.ip_address == "203.0.113.5"
    assert isinstance(reloaded.ip_address, str)

