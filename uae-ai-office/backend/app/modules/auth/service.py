import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password_or_dummy,
)
from app.db.session import set_company_context, set_user_context
from app.modules.audit_log.service import record_audit_event
from app.modules.auth import repository
from app.modules.auth.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    NotAuthenticatedError,
    TooManyAttemptsError,
)
from app.modules.auth.models import RefreshSession, User
from app.modules.auth.rate_limit import login_rate_limiter
from app.modules.auth.schemas import AccessTokenResponse, LoginRequest, SignupRequest
from app.modules.auth.schemas import PasswordChangeRequest, ProfileUpdateRequest


@dataclass
class TokenIssueResult:
    access_token_response: AccessTokenResponse
    raw_refresh_token: str


@dataclass
class TenantContext:
    """The result of fully resolving a request's authorization: which
    user, which company they're acting in, and their DATABASE-authoritative
    role for that company -- never the role claimed by the JWT. This is
    the one object every future tenant-owned module (Projects, Documents,
    Daily Brief, ...) depends on to know both "who" and "with what
    permissions" for the current request.
    """

    user: User
    company_id: uuid.UUID
    role: str


def _access_token_response(*, user_id: uuid.UUID, company_id: uuid.UUID, role: str) -> AccessTokenResponse:
    token = create_access_token(user_id=user_id, company_id=company_id, role=role)
    return AccessTokenResponse(
        access_token=token, expires_in=settings.access_token_expire_minutes * 60
    )


def _issue_refresh_session(
    db: Session, *, user_id: uuid.UUID, company_id: uuid.UUID, family_id: uuid.UUID
) -> tuple[str, RefreshSession]:
    raw_token = generate_refresh_token()
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    session = repository.create_refresh_session(
        db,
        user_id=user_id,
        company_id=company_id,
        token_hash=hash_refresh_token(raw_token),
        family_id=family_id,
        expires_at=expires_at,
    )
    return raw_token, session


def signup(db: Session, data: SignupRequest, *, ip_address: str | None = None) -> TokenIssueResult:
    try:
        company = repository.create_company(
            db, name=data.company_name, timezone=data.timezone, country=data.country
        )
        user = repository.create_user(
            db,
            email=data.email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
        )
        set_company_context(db, company.id)
        repository.create_company_member(
            db, company_id=company.id, user_id=user.id, role="owner"
        )
        # Part of the same transaction as the state change it describes
        # (see the module docstring in audit_log/service.py): if this
        # raises, everything above rolls back too -- signup never
        # "succeeds" without its audit trail.
        record_audit_event(
            db,
            company_id=company.id,
            actor_user_id=user.id,
            action="auth.signup",
            resource_type="user",
            resource_id=user.id,
            metadata={"email": data.email},
            ip_address=ip_address,
        )
    except IntegrityError:
        db.rollback()
        # Generic on purpose: confirms the email is taken (expected/normal
        # for a signup flow) without revealing anything else about the
        # existing account.
        raise EmailAlreadyRegisteredError("An account with this email already exists.") from None

    access_token_response = _access_token_response(
        user_id=user.id, company_id=company.id, role="owner"
    )
    raw_refresh_token, _ = _issue_refresh_session(
        db, user_id=user.id, company_id=company.id, family_id=uuid.uuid4()
    )

    db.commit()
    return TokenIssueResult(
        access_token_response=access_token_response, raw_refresh_token=raw_refresh_token
    )


def _audit_login_failure_if_attributable(
    db: Session, user: User, email: str, ip_address: str | None
) -> None:
    """Only writes an audit row when we can safely attribute the failure
    to a company (i.e. the email matched a real user with a real
    membership) -- audit_logs is company-scoped and there is no company
    to attach an unknown-email attempt to.

    Deliberately best-effort, unlike every other audit call in this
    module: a failed login is not a state change to business data (the
    only thing this path persists is the audit row itself), so a problem
    writing it -- a sanitizer rejection, a transient DB error -- must
    never change the caller's outcome (still a generic 401) or turn an
    authentication failure into an unrelated 500. This is the documented
    exception to "audit writes are transactionally atomic with the
    operation they describe".
    """
    set_user_context(db, user.id)
    memberships = repository.get_own_memberships(db, user.id)
    if not memberships:
        return
    company_id = memberships[0].company_id
    set_company_context(db, company_id)
    try:
        record_audit_event(
            db,
            company_id=company_id,
            actor_user_id=user.id,
            action="auth.login_failure",
            resource_type="user",
            resource_id=user.id,
            metadata={"email": email},
            ip_address=ip_address,
        )
        db.commit()
    except Exception:  # noqa: BLE001 -- deliberately broad, see docstring above
        db.rollback()


def login(
    db: Session, data: LoginRequest, *, ip_address: str | None = None
) -> TokenIssueResult:
    if login_rate_limiter.is_locked(data.email):
        raise TooManyAttemptsError("Too many attempts. Please try again later.")

    user = repository.get_user_by_email(db, data.email)
    password_ok = verify_password_or_dummy(
        data.password, user.password_hash if user is not None else None
    )

    if user is None or not user.is_active or not password_ok:
        login_rate_limiter.record_failure(data.email)
        if user is not None:
            _audit_login_failure_if_attributable(db, user, data.email, ip_address)
        raise InvalidCredentialsError("Invalid email or password.")

    login_rate_limiter.reset(data.email)

    set_user_context(db, user.id)
    memberships = repository.get_own_memberships(db, user.id)
    if not memberships:
        # Should not happen -- signup always creates one membership. Fail
        # the same generic way rather than exposing an internal-state error.
        raise InvalidCredentialsError("Invalid email or password.")
    active_membership = memberships[0]

    now = datetime.now(UTC)
    repository.touch_last_login(db, user.id, now)

    set_company_context(db, active_membership.company_id)
    access_token_response = _access_token_response(
        user_id=user.id, company_id=active_membership.company_id, role=active_membership.role
    )
    raw_refresh_token, _ = _issue_refresh_session(
        db,
        user_id=user.id,
        company_id=active_membership.company_id,
        family_id=uuid.uuid4(),
    )
    record_audit_event(
        db,
        company_id=active_membership.company_id,
        actor_user_id=user.id,
        action="auth.login_success",
        resource_type="user",
        resource_id=user.id,
        metadata={"email": data.email},
        ip_address=ip_address,
    )

    db.commit()
    return TokenIssueResult(
        access_token_response=access_token_response, raw_refresh_token=raw_refresh_token
    )


def update_profile(db: Session, *, user: User, data: ProfileUpdateRequest) -> User:
    updated = repository.update_user_profile(db, user, full_name=data.full_name)
    db.commit()
    return updated


def change_password(db: Session, *, user: User, data: PasswordChangeRequest) -> None:
    if not verify_password_or_dummy(data.current_password, user.password_hash):
        raise InvalidCredentialsError("Current password is incorrect.")
    repository.update_user_password(db, user, password_hash=hash_password(data.new_password))
    repository.revoke_all_user_sessions(db, user.id, when=datetime.now(UTC))
    db.commit()


def switch_company(db: Session, *, user: User, company_id: uuid.UUID) -> TokenIssueResult:
    memberships = repository.get_memberships_with_companies(db, user.id)
    membership = next((member for member, _company in memberships if member.company_id == company_id), None)
    if membership is None:
        raise InvalidCredentialsError("Company membership not found.")
    set_user_context(db, user.id)
    set_company_context(db, company_id)
    access_token_response = _access_token_response(user_id=user.id, company_id=company_id, role=membership.role)
    raw_refresh_token, _ = _issue_refresh_session(db, user_id=user.id, company_id=company_id, family_id=uuid.uuid4())
    db.commit()
    return TokenIssueResult(access_token_response=access_token_response, raw_refresh_token=raw_refresh_token)


def refresh(
    db: Session, raw_refresh_token: str | None, *, ip_address: str | None = None
) -> TokenIssueResult:
    if not raw_refresh_token:
        raise InvalidRefreshTokenError("No refresh session.")

    token_hash = hash_refresh_token(raw_refresh_token)
    session = repository.get_refresh_session_by_hash(db, token_hash)
    if session is None:
        raise InvalidRefreshTokenError("No refresh session.")

    now = datetime.now(UTC)

    if session.revoked_at is not None:
        # A revoked/already-rotated token being presented again means
        # this token has leaked -- kill every session descended from it,
        # not just this one. A real security-relevant state change, so
        # (unlike login failure) this audit write stays atomic with it.
        repository.revoke_family(db, session.family_id, when=now)
        set_company_context(db, session.company_id)
        record_audit_event(
            db,
            company_id=session.company_id,
            actor_user_id=session.user_id,
            action="auth.refresh_reuse_detected",
            resource_type="refresh_session",
            resource_id=session.id,
            ip_address=ip_address,
        )
        db.commit()
        raise InvalidRefreshTokenError("Refresh session is no longer valid.")

    if session.expires_at <= now:
        raise InvalidRefreshTokenError("Refresh session has expired.")

    user = repository.get_user_by_id(db, session.user_id)
    if user is None or not user.is_active:
        raise InvalidRefreshTokenError("Refresh session is no longer valid.")

    set_company_context(db, session.company_id)
    membership = repository.get_membership(db, session.user_id, session.company_id)
    if membership is None:
        # Membership was revoked since this session was issued --
        # re-verified here, not trusted from the token/session alone.
        raise InvalidRefreshTokenError("Refresh session is no longer valid.")

    raw_new_token, new_session = _issue_refresh_session(
        db, user_id=user.id, company_id=session.company_id, family_id=session.family_id
    )
    repository.revoke_refresh_session(
        db, session, when=now, replaced_by_id=new_session.id
    )

    access_token_response = _access_token_response(
        user_id=user.id, company_id=session.company_id, role=membership.role
    )

    db.commit()
    return TokenIssueResult(
        access_token_response=access_token_response, raw_refresh_token=raw_new_token
    )


def logout(
    db: Session, raw_refresh_token: str | None, *, ip_address: str | None = None
) -> None:
    if not raw_refresh_token:
        return  # idempotent: nothing to revoke

    token_hash = hash_refresh_token(raw_refresh_token)
    session = repository.get_refresh_session_by_hash(db, token_hash)
    if session is None or session.revoked_at is not None:
        return  # idempotent

    now = datetime.now(UTC)
    repository.revoke_refresh_session(db, session, when=now)
    set_company_context(db, session.company_id)
    record_audit_event(
        db,
        company_id=session.company_id,
        actor_user_id=session.user_id,
        action="auth.logout",
        resource_type="refresh_session",
        resource_id=session.id,
        ip_address=ip_address,
    )
    db.commit()


def decode_bearer_token(access_token: str) -> dict:
    """Step 1 of the authoritative request flow: validate JWT signature,
    type, and expiration. Nothing about the user or their membership is
    checked yet -- that's deliberately separate (see get_user_from_payload
    and get_tenant_context below), so a caller that only needs "is this a
    validly-signed token" doesn't have to pull in a DB round trip.
    """
    try:
        return decode_access_token(access_token)
    except InvalidTokenError:
        raise NotAuthenticatedError("Invalid or expired access token.") from None


def get_user_from_payload(db: Session, payload: dict) -> User:
    """Steps 2-3: resolve the user from the JWT's `sub` claim and confirm
    they still exist and are active. This is the reusable "authenticated
    user" building block -- it deliberately does NOT touch company
    context, so it's usable by any future endpoint that needs "who is
    this" without needing "which company" (e.g. listing a user's own
    memberships across companies).
    """
    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        # A malformed claim can only come from a token that wasn't issued
        # by create_access_token -- treat it the same as any other
        # invalid token rather than letting a ValueError/KeyError surface
        # as an unhandled 500.
        raise NotAuthenticatedError("Invalid or expired access token.") from None

    user = repository.get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise NotAuthenticatedError("Invalid or expired access token.")
    return user


def get_tenant_context(db: Session, payload: dict, user: User) -> TenantContext:
    """Steps 4-8 of the authoritative request flow: resolve the active
    company from the token, re-verify membership against the database
    (never trusting the JWT's company_id as proof of authorization or its
    role claim as authorization), and set the transaction-local RLS
    context. Every tenant-owned query executed after this call -- by this
    endpoint or any repository it calls -- is scoped by these two SET
    LOCAL values plus RLS as the second, independent layer.
    """
    try:
        company_id = uuid.UUID(payload["company_id"])
    except (ValueError, KeyError):
        raise NotAuthenticatedError("Invalid or expired access token.") from None

    set_user_context(db, user.id)
    set_company_context(db, company_id)

    membership = repository.get_membership(db, user.id, company_id)
    if membership is None:
        # Covers both "never was a member" and "membership since removed"
        # -- an otherwise-valid, unexpired JWT is not enough on its own.
        raise NotAuthenticatedError("Invalid or expired access token.")

    return TenantContext(user=user, company_id=company_id, role=membership.role)

