import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.auth.models import RefreshSession, User
from app.modules.tenancy.models import Company, CompanyMember


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def create_user(db: Session, *, email: str, password_hash: str, full_name: str) -> User:
    user = User(email=email, password_hash=password_hash, full_name=full_name)
    db.add(user)
    db.flush()
    return user


def touch_last_login(db: Session, user_id: uuid.UUID, when: datetime) -> None:
    db.execute(update(User).where(User.id == user_id).values(last_login_at=when))


def create_company(db: Session, *, name: str, timezone: str, country: str) -> Company:
    company = Company(name=name, timezone=timezone, country=country)
    db.add(company)
    db.flush()
    return company


def create_company_member(
    db: Session, *, company_id: uuid.UUID, user_id: uuid.UUID, role: str
) -> CompanyMember:
    member = CompanyMember(company_id=company_id, user_id=user_id, role=role)
    db.add(member)
    db.flush()
    return member


def get_own_memberships(db: Session, user_id: uuid.UUID) -> list[CompanyMember]:
    """Relies on company_members' self-lookup RLS policy -- the caller
    must have called set_user_context(db, user_id) first. Ordered oldest
    first so "the first company this user was ever part of" is a stable,
    deterministic choice of active company until a real company-switcher
    exists.
    """
    return list(
        db.execute(
            select(CompanyMember)
            .where(CompanyMember.user_id == user_id)
            .order_by(CompanyMember.created_at.asc())
        ).scalars()
    )


def get_membership(
    db: Session, user_id: uuid.UUID, company_id: uuid.UUID
) -> CompanyMember | None:
    """Relies on the normal tenant_isolation RLS policy -- the caller
    must have called set_company_context(db, company_id) first.
    """
    return db.execute(
        select(CompanyMember).where(
            CompanyMember.user_id == user_id, CompanyMember.company_id == company_id
        )
    ).scalar_one_or_none()


def create_refresh_session(
    db: Session,
    *,
    user_id: uuid.UUID,
    company_id: uuid.UUID,
    token_hash: str,
    family_id: uuid.UUID,
    expires_at: datetime,
) -> RefreshSession:
    session = RefreshSession(
        user_id=user_id,
        company_id=company_id,
        token_hash=token_hash,
        family_id=family_id,
        expires_at=expires_at,
    )
    db.add(session)
    db.flush()
    return session


def get_refresh_session_by_hash(db: Session, token_hash: str) -> RefreshSession | None:
    return db.execute(
        select(RefreshSession).where(RefreshSession.token_hash == token_hash)
    ).scalar_one_or_none()


def revoke_refresh_session(
    db: Session, session: RefreshSession, *, when: datetime, replaced_by_id: uuid.UUID | None = None
) -> None:
    session.revoked_at = when
    if replaced_by_id is not None:
        session.replaced_by_id = replaced_by_id
    db.flush()


def revoke_family(db: Session, family_id: uuid.UUID, *, when: datetime) -> None:
    db.execute(
        update(RefreshSession)
        .where(RefreshSession.family_id == family_id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=when)
    )

