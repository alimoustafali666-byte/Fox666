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


class InvitationNotFoundError(AppError):
    status_code = 404
    code = "invitation_not_found"


class InvitationInvalidError(AppError):
    status_code = 400
    code = "invitation_invalid"


class InvitationAlreadyExistsError(AppError):
    status_code = 409
    code = "invitation_already_exists"


class InvitationExistingAccountError(AppError):
    """The invited address already has a UAE AI Office account, and the
    password supplied to accept the invitation was not that account's
    password.

    Accepting an invitation issues a full session for the invited
    address. When no account exists yet, the invitation link is the only
    thing proving control of that address and the caller sets the
    password themselves. When an account *already* exists, the link
    alone must not be enough: an owner/admin can invite any address they
    like and reads the raw token straight out of the create-invitation
    response, so an unchecked accept would hand them a logged-in session
    for somebody else's existing account -- and, via
    /auth/me/companies/switch, that person's other companies too.

    So an existing account must prove itself with its own password
    before the membership is granted. Deliberately 401 with the same
    shape as a failed login: it is exactly a failed authentication.
    """

    status_code = 401
    code = "invitation_existing_account"
