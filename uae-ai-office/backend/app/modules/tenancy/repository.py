import uuid

from datetime import date, datetime, time

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.tenancy.models import Company, CompanyInvitation, CompanyMember


def get_company_by_id(db: Session, company_id: uuid.UUID) -> Company | None:
    """companies has no RLS (it's the tenant root, not tenant-owned), so
    this is a plain lookup by id. Safe to call only after a caller has
    already established (via get_tenant_context) that the current user
    is actually a member of this company -- this function itself does
    not check that.
    """
    return db.get(Company, company_id)


def list_company_members_with_user_info(
    db: Session, company_id: uuid.UUID
) -> list[tuple[CompanyMember, User]]:
    """Relies on company_members' tenant_isolation RLS policy: the caller
    must have already called set_company_context(db, company_id) (which
    get_tenant_context does). The company_id parameter here is passed
    explicitly for query clarity/an extra defense-in-depth filter, not as
    the sole isolation mechanism -- even if this were called with a
    different (wrong) company_id than the active RLS context, RLS would
    still only return rows matching the context, never the parameter.
    """
    rows = db.execute(
        select(CompanyMember, User)
        .join(User, User.id == CompanyMember.user_id)
        .where(CompanyMember.company_id == company_id)
        .order_by(CompanyMember.created_at.asc())
    ).all()
    return [(member, user) for member, user in rows]


def update_company(
    db: Session,
    *,
    company_id: uuid.UUID,
    name: str | None,
    timezone: str | None,
    country: str | None,
) -> Company:
    """`companies` has no RLS of its own (see get_company_by_id's
    docstring) -- callers must have already verified, via
    get_tenant_context/require_roles, that the actor is an owner/admin
    member of THIS company_id before calling this.
    """
    company = db.get(Company, company_id)
    if name is not None:
        company.name = name
    if timezone is not None:
        company.timezone = timezone
    if country is not None:
        company.country = country
    db.flush()
    return company


def claim_daily_brief_schedule_date(db: Session, *, company_id: uuid.UUID, scheduled_date: date) -> bool:
    result = db.execute(
        update(Company)
        .where(
            Company.id == company_id,
            Company.daily_brief_schedule_enabled.is_(True),
            (Company.daily_brief_last_scheduled_date.is_(None) | (Company.daily_brief_last_scheduled_date < scheduled_date)),
        )
        .values(daily_brief_last_scheduled_date=scheduled_date)
    )
    db.flush()
    return result.rowcount == 1


def update_daily_brief_schedule(db: Session, *, company_id: uuid.UUID, enabled: bool, schedule_time: time) -> Company:
    company = db.get(Company, company_id)
    company.daily_brief_schedule_enabled = enabled
    company.daily_brief_schedule_time = schedule_time
    db.flush()
    return company


def list_scheduled_companies(db: Session) -> list[Company]:
    return list(db.execute(select(Company).where(Company.daily_brief_schedule_enabled.is_(True))).scalars())


def get_company_owner(db: Session, company_id: uuid.UUID) -> CompanyMember | None:
    return db.execute(select(CompanyMember).where(
        CompanyMember.company_id == company_id, CompanyMember.role == "owner"
    ).order_by(CompanyMember.created_at.asc()).limit(1)).scalar_one_or_none()


def set_company_logo(
    db: Session, *, company_id: uuid.UUID, storage_key: str | None, content_type: str | None
) -> Company:
    company = db.get(Company, company_id)
    company.logo_storage_key = storage_key
    company.logo_content_type = content_type
    db.flush()
    return company


def count_members_by_role(db: Session, *, company_id: uuid.UUID, role: str) -> int:
    """Relies on company_members' tenant_isolation RLS policy, same as
    list_company_members_with_user_info above.
    """
    return db.execute(
        select(func.count())
        .select_from(CompanyMember)
        .where(CompanyMember.company_id == company_id, CompanyMember.role == role)
    ).scalar_one()


def update_member_role(db: Session, *, member: CompanyMember, role: str) -> CompanyMember:
    member.role = role
    db.flush()
    return member


def delete_member(db: Session, *, member: CompanyMember) -> None:
    db.delete(member)
    db.flush()


def create_invitation(
    db: Session, *, company_id: uuid.UUID, email: str, role: str, invited_by: uuid.UUID,
    token_hash: str, expires_at: datetime
) -> CompanyInvitation:
    invitation = CompanyInvitation(
        company_id=company_id, email=email, role=role, invited_by=invited_by,
        token_hash=token_hash, expires_at=expires_at
    )
    db.add(invitation)
    db.flush()
    return invitation


def get_invitation_by_token_hash(db: Session, token_hash: str) -> CompanyInvitation | None:
    return db.execute(select(CompanyInvitation).where(CompanyInvitation.token_hash == token_hash)).scalar_one_or_none()


def get_invitation(db: Session, company_id: uuid.UUID, invitation_id: uuid.UUID) -> CompanyInvitation | None:
    return db.execute(select(CompanyInvitation).where(
        CompanyInvitation.id == invitation_id, CompanyInvitation.company_id == company_id
    )).scalar_one_or_none()


def list_invitations(db: Session, company_id: uuid.UUID) -> list[CompanyInvitation]:
    return list(db.execute(select(CompanyInvitation).where(
        CompanyInvitation.company_id == company_id
    ).order_by(CompanyInvitation.created_at.desc())).scalars())

