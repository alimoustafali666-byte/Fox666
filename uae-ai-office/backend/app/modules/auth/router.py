from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.request_ip import get_client_ip
from app.db.session import get_db
from app.modules.auth import service
from app.modules.auth.dependencies import get_current_user, get_tenant_context
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    AccessTokenResponse,
    CompanyMembershipPublic,
    CompanySwitchRequest,
    LoginRequest,
    MeResponse,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    SignupRequest,
    UserPublic,
)
from app.modules.auth.service import TenantContext
from app.modules.tenancy import service as tenancy_service
from app.modules.tenancy.models import Company
from app.modules.tenancy.schemas import (
    InvitationAcceptRequest,
    InvitationPreviewResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        # Scoped to the auth routes only: the browser never attaches this
        # cookie to any other request, minimizing where it's exposed.
        path="/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    # secure/samesite must match what set_cookie used, or the browser
    # treats the deletion as a *different* cookie and leaves the original
    # in place (this is what makes logout appear not to stick when the
    # cookie is cross-site).
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path="/v1/auth",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        httponly=True,
    )


@router.post("/signup", response_model=AccessTokenResponse, status_code=status.HTTP_201_CREATED)
def signup(
    data: SignupRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> AccessTokenResponse:
    result = service.signup(db, data, ip_address=get_client_ip(request))
    _set_refresh_cookie(response, result.raw_refresh_token)
    return result.access_token_response


@router.post("/login", response_model=AccessTokenResponse)
def login(
    data: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> AccessTokenResponse:
    result = service.login(db, data, ip_address=get_client_ip(request))
    _set_refresh_cookie(response, result.raw_refresh_token)
    return result.access_token_response


# Unauthenticated by design: the holder of the link is, at this point,
# exactly who this endpoint exists to serve. It returns only what is
# needed to recognise the invitation and render the right form, and a
# token that is expired, revoked or already accepted is indistinguishable
# from one that never existed (both 400 invitation_invalid).
@router.get("/invitations/{token}", response_model=InvitationPreviewResponse)
def preview_invitation(token: str, db: Session = Depends(get_db)) -> InvitationPreviewResponse:
    invitation = tenancy_service.get_invitation_for_acceptance(db, token)
    company = db.get(Company, invitation.company_id)
    return InvitationPreviewResponse(
        email=str(invitation.email),
        company_name=company.name if company else "",
        role=invitation.role,
        expires_at=invitation.expires_at,
        requires_existing_password=tenancy_service.invitation_requires_existing_password(
            db, invitation
        ),
    )


@router.post("/invitations/{token}/accept", response_model=AccessTokenResponse)
def accept_invitation(
    token: str,
    data: InvitationAcceptRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    invitation = tenancy_service.get_invitation_for_acceptance(db, token)
    result, raw_refresh_token = tenancy_service.accept_invitation(
        db,
        raw_token=token,
        email=str(invitation.email),
        password=data.password,
        full_name=data.full_name,
    )
    _set_refresh_cookie(response, raw_refresh_token)
    return result


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    request: Request, response: Response, db: Session = Depends(get_db)
) -> AccessTokenResponse:
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    result = service.refresh(db, raw_token, ip_address=get_client_ip(request))
    _set_refresh_cookie(response, result.raw_refresh_token)
    return result.access_token_response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    service.logout(db, raw_token, ip_address=get_client_ip(request))
    _clear_refresh_cookie(response)


@router.get("/me", response_model=MeResponse)
def me(context: TenantContext = Depends(get_tenant_context)) -> MeResponse:
    return MeResponse(
        user=UserPublic(
            id=context.user.id,
            email=context.user.email,
            full_name=context.user.full_name,
            is_active=context.user.is_active,
            created_at=context.user.created_at,
        ),
        company_id=context.company_id,
        role=context.role,
    )


@router.patch("/me", response_model=UserPublic)
def update_profile(
    data: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserPublic:
    updated = service.update_profile(db, user=user, data=data)
    return UserPublic(id=updated.id, email=updated.email, full_name=updated.full_name, is_active=updated.is_active, created_at=updated.created_at)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    service.change_password(db, user=user, data=data)


@router.get("/me/companies", response_model=list[CompanyMembershipPublic])
def list_my_companies(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[CompanyMembershipPublic]:
    return [CompanyMembershipPublic(company_id=member.company_id, company_name=company.name, role=member.role) for member, company in service.repository.get_memberships_with_companies(db, user.id)]


@router.post("/me/companies/switch", response_model=AccessTokenResponse)
def switch_company(
    data: CompanySwitchRequest, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AccessTokenResponse:
    result = service.switch_company(db, user=user, company_id=data.company_id)
    _set_refresh_cookie(response, result.raw_refresh_token)
    return result.access_token_response

