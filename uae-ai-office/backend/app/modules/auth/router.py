from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.request_ip import get_client_ip
from app.db.session import get_db
from app.modules.auth import service
from app.modules.auth.dependencies import get_tenant_context
from app.modules.auth.schemas import (
    AccessTokenResponse,
    LoginRequest,
    MeResponse,
    SignupRequest,
    UserPublic,
)
from app.modules.auth.service import TenantContext

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        # Scoped to the auth routes only: the browser never attaches this
        # cookie to any other request, minimizing where it's exposed.
        path="/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.refresh_cookie_name, path="/v1/auth")


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

