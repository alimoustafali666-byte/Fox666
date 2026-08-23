from app.core.exceptions import AppError


class EmailAlreadyRegisteredError(AppError):
    status_code = 409
    code = "email_already_registered"


class InvalidCredentialsError(AppError):
    """Deliberately used for every login failure reason (wrong password,
    unknown email, inactive user) -- the response must never let a caller
    distinguish between them.
    """

    status_code = 401
    code = "invalid_credentials"


class TooManyAttemptsError(AppError):
    status_code = 429
    code = "too_many_attempts"


class InvalidRefreshTokenError(AppError):
    """Used for a missing, unknown, expired, already-rotated, revoked, or
    reused refresh token alike -- same reasoning as InvalidCredentialsError.
    """

    status_code = 401
    code = "invalid_refresh_token"


class NotAuthenticatedError(AppError):
    """Used for every reason a tenant context could not be established:
    missing/invalid/expired token, inactive user, membership no longer
    exists for the token's company. Deliberately generic for the same
    reason as InvalidCredentialsError -- none of these should be
    distinguishable from one another by the caller.
    """

    status_code = 401
    code = "not_authenticated"


class ForbiddenError(AppError):
    """The caller IS authenticated with a valid tenant context, but their
    (database-authoritative) role does not permit this action. Distinct
    from NotAuthenticatedError on purpose -- "who you are" was resolved
    successfully, "what you're allowed to do" is what failed.
    """

    status_code = 403
    code = "forbidden"

