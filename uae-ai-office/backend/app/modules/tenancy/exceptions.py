from app.core.exceptions import AppError


class MemberNotFoundError(AppError):
    """The target user isn't a member of the acting company -- identical
    for "never was" and "belongs to another company", same IDOR
    discipline used throughout this app.
    """

    status_code = 404
    code = "member_not_found"


class InvalidRoleError(AppError):
    status_code = 400
    code = "invalid_role"


class LastOwnerError(AppError):
    """A company must always retain at least one owner -- refused for
    both demoting and removing the last remaining owner.
    """

    status_code = 400
    code = "last_owner"


class InsufficientRoleForActionError(AppError):
    """An admin (not an owner) tried to modify or remove an owner-level
    member, or tried to promote someone TO owner -- privilege
    escalation/owner-tampering that require_roles("owner", "admin")
    alone doesn't prevent, since it only checks the ACTOR's role, not
    the TARGET's.
    """

    status_code = 403
    code = "insufficient_role_for_action"


class UnsupportedLogoTypeError(AppError):
    status_code = 400
    code = "unsupported_logo_type"


class LogoTooLargeError(AppError):
    status_code = 400
    code = "logo_too_large"


class LogoNotFoundError(AppError):
    status_code = 404
    code = "logo_not_found"


class LogoStorageUnavailableError(AppError):
    status_code = 503
    code = "logo_storage_unavailable"


class CannotRemoveSelfError(AppError):
    """Self-removal ("leave the company") would strand the acting user
    with zero company memberships -- login/signup in this app assumes
    every user belongs to at least one company, and there is no
    "join an existing company" flow yet to recover from that state. A
    deliberately out-of-scope feature for this step; see the Step 20
    report.
    """

    status_code = 400
    code = "cannot_remove_self"

