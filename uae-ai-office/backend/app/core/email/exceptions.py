"""Typed exceptions for the transactional-email abstraction. Mirrors
app.core.storage.exceptions / app.core.llm.exceptions in shape and
rationale: deliberately NOT AppError subclasses (this is a lower-level
infrastructure concern), and no raise site in this package or any
provider implementation ever puts an API key, an SMTP password, an
Authorization header, or a raw vendor response body into a message.

Provider responses are summarized (status code, a short reason) but the
credential material used to authenticate is never echoed anywhere.
"""


class EmailError(Exception):
    error_code: str = "email_failed"


class EmailUnavailable(EmailError):
    """Transient: connection/timeout/5xx-shaped failure, or a rate-limit
    response. The same message may reasonably be retried later (in this
    app, by the operator pressing "Resend invitation").
    """

    error_code = "email_provider_unavailable"


class EmailAuthenticationError(EmailError):
    """The provider rejected the configured credential (401/403-shaped,
    or an SMTP 535). Never retried -- a bad credential fails identically
    every time.
    """

    error_code = "email_provider_authentication_failed"


class EmailConfigurationError(EmailError):
    """Required configuration is missing or invalid for the selected
    provider (e.g. EMAIL_PROVIDER is 'resend' but RESEND_API_KEY is not
    set). Raised eagerly, at provider-construction time, rather than
    surfacing later as a confusing vendor error.
    """

    error_code = "email_provider_misconfigured"


class EmailRecipientRejectedError(EmailError):
    """The provider accepted the request but refused this specific
    recipient or sender -- an unverified sending domain, a suppressed
    address, a malformed mailbox. Retrying the identical message will
    fail identically; the configuration or the address has to change.
    """

    error_code = "email_recipient_rejected"


class EmailOperationError(EmailError):
    """Catch-all for a provider-reported failure that is neither an
    authentication problem nor clearly transient.
    """

    error_code = "email_operation_failed"
