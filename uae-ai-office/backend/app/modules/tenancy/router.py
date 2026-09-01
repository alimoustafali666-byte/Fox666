import uuid

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.request_ip import get_client_ip
from app.db.session import get_db
from app.modules.auth import repository as auth_repository
from app.modules.auth.dependencies import get_tenant_context, require_roles
from app.modules.auth.service import TenantContext
from app.modules.tenancy import repository, service
from app.modules.tenancy.models import Company
from app.modules.tenancy.schemas import (
    CompanyMemberPublic,
    CompanyPublic,
    CompanyUpdateRequest,
    CurrentCompanyResponse,
    MemberRoleUpdateRequest,
    DailyBriefSchedulePublic,
    DailyBriefScheduleUpdateRequest,
    InvitationCreateRequest,
    InvitationCreateResponse,
    InvitationPublic,
)

router = APIRouter(prefix="/companies", tags=["tenancy"])


def _company_public(company) -> CompanyPublic:
    return CompanyPublic(
        id=company.id,
        name=company.name,
        timezone=company.timezone,
        country=company.country,
        has_logo=bool(company.logo_storage_key),
    )


def _schedule_public(company: Company) -> DailyBriefSchedulePublic:
    return DailyBriefSchedulePublic(
        enabled=company.daily_brief_schedule_enabled,
        time=company.daily_brief_schedule_time,
        timezone=company.timezone,
        last_scheduled_date=company.daily_brief_last_scheduled_date,
    )


@router.get("/current", response_model=CurrentCompanyResponse)
def get_current_company(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> CurrentCompanyResponse:
    company = repository.get_company_by_id(db, context.company_id)
    return CurrentCompanyResponse(
        company=_company_public(company),
        # The database-authoritative role resolved by get_tenant_context,
        # not anything read back off the request's JWT.
        role=context.role,
    )


@router.patch("/current", response_model=CurrentCompanyResponse)
def update_current_company(
    body: CompanyUpdateRequest,
    request: Request,
    context: TenantContext = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> CurrentCompanyResponse:
    company = service.update_company(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        name=body.name,
        timezone=body.timezone,
        country=body.country,
        ip_address=get_client_ip(request),
    )
    return CurrentCompanyResponse(company=_company_public(company), role=context.role)


@router.get("/current/daily-brief-schedule", response_model=DailyBriefSchedulePublic)
def get_daily_brief_schedule(
    context: TenantContext = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> DailyBriefSchedulePublic:
    return _schedule_public(repository.get_company_by_id(db, context.company_id))


@router.patch("/current/daily-brief-schedule", response_model=DailyBriefSchedulePublic)
def update_daily_brief_schedule(
    body: DailyBriefScheduleUpdateRequest,
    context: TenantContext = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> DailyBriefSchedulePublic:
    company = repository.update_daily_brief_schedule(
        db, company_id=context.company_id, enabled=body.enabled, schedule_time=body.time
    )
    db.commit()
    return _schedule_public(company)


@router.post("/current/logo", response_model=CompanyPublic)
def upload_current_company_logo(
    request: Request,
    file: UploadFile = File(...),
    context: TenantContext = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> CompanyPublic:
    company = service.upload_company_logo(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        upload_file=file,
        ip_address=get_client_ip(request),
    )
    return _company_public(company)


@router.delete("/current/logo", response_model=CompanyPublic)
def delete_current_company_logo(
    request: Request,
    context: TenantContext = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> CompanyPublic:
    company = service.delete_company_logo(
        db, company_id=context.company_id, actor_user_id=context.user.id, ip_address=get_client_ip(request)
    )
    return _company_public(company)


@router.get("/current/logo")
def get_current_company_logo(
    # Any authenticated company member may view the logo -- it's shown
    # in the app shell to every role, not just management.
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> Response:
    data, content_type = service.get_company_logo_bytes(db, company_id=context.company_id)
    return Response(content=data, media_type=content_type)


@router.get("/current/members", response_model=list[CompanyMemberPublic])
def list_current_company_members(
    context: TenantContext = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> list[CompanyMemberPublic]:
    rows = repository.list_company_members_with_user_info(db, context.company_id)
    return [
        CompanyMemberPublic(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=member.role,
            created_at=member.created_at,
        )
        for member, user in rows
    ]


@router.patch("/current/members/{user_id}", response_model=CompanyMemberPublic)
def update_current_company_member_role(
    user_id: uuid.UUID,
    body: MemberRoleUpdateRequest,
    request: Request,
    context: TenantContext = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> CompanyMemberPublic:
    member = service.change_member_role(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        actor_role=context.role,
        target_user_id=user_id,
        new_role=body.role,
        ip_address=get_client_ip(request),
    )
    user = auth_repository.get_user_by_id(db, user_id)
    return CompanyMemberPublic(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=member.role,
        created_at=member.created_at,
    )


@router.delete("/current/members/{user_id}", status_code=204)
def remove_current_company_member(
    user_id: uuid.UUID,
    request: Request,
    context: TenantContext = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> None:
    service.remove_member(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        actor_role=context.role,
        target_user_id=user_id,
        ip_address=get_client_ip(request),
    )


def _invitation_public(invitation) -> InvitationPublic:
    return InvitationPublic(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        status=service.invitation_status(invitation),
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
    )


@router.get("/current/invitations", response_model=list[InvitationPublic])
def list_current_company_invitations(
    context: TenantContext = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> list[InvitationPublic]:
    return [_invitation_public(item) for item in service.list_company_invitations(db, context.company_id)]


@router.post("/current/invitations", response_model=InvitationCreateResponse, status_code=201)
def invite_company_user(
    body: InvitationCreateRequest,
    context: TenantContext = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> InvitationCreateResponse:
    invitation, token = service.create_invitation(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        email=str(body.email),
        role=body.role,
    )
    return InvitationCreateResponse(**_invitation_public(invitation).model_dump(), token=token)


@router.post("/current/invitations/{invitation_id}/resend", response_model=InvitationCreateResponse)
def resend_company_invitation(
    invitation_id: uuid.UUID,
    context: TenantContext = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> InvitationCreateResponse:
    invitation, token = service.resend_invitation(
        db, company_id=context.company_id, invitation_id=invitation_id
    )
    return InvitationCreateResponse(**_invitation_public(invitation).model_dump(), token=token)


@router.delete("/current/invitations/{invitation_id}", status_code=204)
def cancel_company_invitation(
    invitation_id: uuid.UUID,
    context: TenantContext = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> None:
    service.revoke_invitation(db, company_id=context.company_id, invitation_id=invitation_id)

