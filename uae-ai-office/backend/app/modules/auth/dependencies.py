from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.exceptions import ForbiddenError, NotAuthenticatedError
from app.modules.auth.models import User
from app.modules.auth.service import TenantContext
from app.modules.auth.service import decode_bearer_token as _decode_bearer_token
from app.modules.auth.service import get_tenant_context as _get_tenant_context
from app.modules.auth.service import get_user_from_payload as _get_user_from_payload

_bearer_scheme = HTTPBearer(auto_error=False)


def get_bearer_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """Base of the whole dependency chain below. FastAPI caches a
    dependency's result per request by default, so even though both
    get_current_user and get_tenant_context depend on this, the token is
    decoded exactly once per request.
    """
    if credentials is None:
        raise NotAuthenticatedError("Authentication required.")
    return _decode_bearer_token(credentials.credentials)


def get_current_user(
    payload: dict = Depends(get_bearer_payload),
    db: Session = Depends(get_db),
) -> User:
    """Reusable "who is making this request" dependency -- no company/RLS
    context involved. Use this directly only for endpoints that
    genuinely don't need tenant scoping; every tenant-owned endpoint
    should depend on get_tenant_context (or require_roles(...)) instead.
    """
    return _get_user_from_payload(db, payload)


def get_tenant_context(
    payload: dict = Depends(get_bearer_payload),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenantContext:
    """The reusable tenant-authorization dependency every tenant-owned
    endpoint (this step's company endpoints, and every future Projects/
    Documents/Daily Brief/Tasks endpoint) should depend on. Resolves and
    returns the authenticated user, their active company, and their
    database-authoritative role, and sets the transaction-local RLS
    context (app.current_user_id, app.current_company_id) as a side
    effect so subsequent queries in this request are correctly scoped.
    """
    return _get_tenant_context(db, payload, user)


def require_roles(*allowed_roles: str) -> Callable[[TenantContext], TenantContext]:
    """FastAPI dependency factory for role-gated endpoints. Always takes
    an explicit allow-list -- it does not expand a role via any assumed
    hierarchy (owner > admin > manager > member is documented as a fact
    in app.modules.tenancy.roles.ROLE_HIERARCHY, but callers must opt in
    to which specific roles a given endpoint allows).

    Usage: Depends(require_roles("owner", "admin"))
    """
    allowed = set(allowed_roles)

    def dependency(context: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if context.role not in allowed:
            raise ForbiddenError("You do not have permission to perform this action.")
        return context

    return dependency

