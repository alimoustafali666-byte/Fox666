"""Step 5's documented audit-failure policy, exercised concretely through
auth.service (the first real caller of record_audit_event):

- signup is a state change; if writing its audit event fails, the whole
  operation must roll back -- it must never appear to succeed with a
  missing audit trail.
- a login failure is not a state change to business data; if writing
  its audit event fails, the caller must still get the normal 401
  outcome, not an unrelated error.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth import service
from app.modules.auth.exceptions import InvalidCredentialsError
from app.modules.auth.models import User
from app.modules.auth.schemas import LoginRequest, SignupRequest
from app.modules.tenancy.models import Company


def _boom(*args, **kwargs):
    raise RuntimeError("simulated audit write failure")


SIGNUP_DATA = SignupRequest(
    email="failure-policy@example.com",
    password="correct horse battery staple",
    full_name="Failure Policy",
    company_name="Failure Policy Co",
)


def test_signup_rolls_back_entirely_if_its_audit_write_fails(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(service, "record_audit_event", _boom)

    raised = False
    try:
        service.signup(db_session, SIGNUP_DATA)
    except RuntimeError:
        raised = True
        db_session.rollback()

    assert raised, "a failed audit write must not let signup silently succeed"

    # Nothing from the attempted signup should have been persisted --
    # atomicity means all or nothing.
    company = db_session.execute(
        select(Company).where(Company.name == SIGNUP_DATA.company_name)
    ).scalar_one_or_none()
    user = db_session.execute(
        select(User).where(User.email == SIGNUP_DATA.email)
    ).scalar_one_or_none()
    assert company is None
    assert user is None


def test_login_failure_still_returns_normal_error_if_its_audit_write_fails(
    db_session: Session, monkeypatch
) -> None:
    # First, a real signup (audit service NOT patched yet) so there's a
    # real user to fail a login against.
    service.signup(db_session, SIGNUP_DATA)
    db_session.commit()

    monkeypatch.setattr(service, "record_audit_event", _boom)

    try:
        service.login(
            db_session,
            LoginRequest(email=SIGNUP_DATA.email, password="the-wrong-password-here"),
        )
        raised_correct_error = False
    except InvalidCredentialsError:
        raised_correct_error = True
    except RuntimeError:
        raised_correct_error = False

    assert raised_correct_error, (
        "a failed *login-failure* audit write must not change the caller's "
        "outcome -- still a generic InvalidCredentialsError, never the "
        "audit failure itself leaking out as an unrelated error"
    )

