"""The only place application code should construct an EmailProvider.
Business/domain code (app.modules.tenancy's invitation flow) depends on
get_email_provider() and the EmailProvider interface -- never on
SmtpEmailProvider, ResendEmailProvider, smtplib or httpx directly.
Mirrors app.core.storage.factory and app.core.llm.factory exactly.

Unlike those two, EMAIL_PROVIDER has no default. Storage and the LLM
default to a real provider because a missing credential there fails
visibly on first use. Mail is different: the harm of a
silently-unconfigured mailer is that it looks like it worked. Requiring
the setting explicitly, and refusing to build anything without it, is
what makes "no email provider configured" an error the operator sees
rather than an invitation nobody ever receives.
"""

from app.core.config import settings
from app.core.email.exceptions import EmailConfigurationError
from app.core.email.provider import EmailProvider
from app.core.email.resend_provider import ResendEmailProvider
from app.core.email.smtp_provider import SmtpEmailProvider

_provider: EmailProvider | None = None


def _require_from_address() -> str:
    if not settings.email_from_address:
        raise EmailConfigurationError(
            "Email is enabled but EMAIL_FROM_ADDRESS is not configured."
        )
    return settings.email_from_address


def _build_resend_provider() -> ResendEmailProvider:
    if not settings.resend_api_key:
        raise EmailConfigurationError(
            "EMAIL_PROVIDER is 'resend' but RESEND_API_KEY is not configured."
        )
    return ResendEmailProvider(
        api_key=settings.resend_api_key,
        from_address=_require_from_address(),
        from_name=settings.email_from_name or None,
        reply_to=settings.email_reply_to,
        timeout_seconds=settings.email_timeout_seconds,
    )


def _build_smtp_provider() -> SmtpEmailProvider:
    missing = [
        name
        for name, value in (
            ("SMTP_HOST", settings.smtp_host),
            ("SMTP_USERNAME", settings.smtp_username),
            ("SMTP_PASSWORD", settings.smtp_password),
        )
        if not value
    ]
    if missing:
        raise EmailConfigurationError(
            "EMAIL_PROVIDER is 'smtp' but required configuration is missing: "
            + ", ".join(missing)
        )
    return SmtpEmailProvider(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password,
        from_address=_require_from_address(),
        from_name=settings.email_from_name or None,
        reply_to=settings.email_reply_to,
        use_starttls=settings.smtp_use_starttls,
        use_ssl=settings.smtp_use_ssl,
        timeout_seconds=settings.email_timeout_seconds,
    )


def _build_provider() -> EmailProvider:
    provider = (settings.email_provider or "").strip().lower()
    if not provider:
        raise EmailConfigurationError(
            "No email provider is configured. Set EMAIL_PROVIDER to 'resend' "
            "or 'smtp' (plus that provider's credentials and "
            "EMAIL_FROM_ADDRESS) to have invitations delivered by email."
        )
    if provider == "resend":
        return _build_resend_provider()
    if provider == "smtp":
        return _build_smtp_provider()
    raise EmailConfigurationError(
        f"Unknown EMAIL_PROVIDER '{provider}' (expected 'resend' or 'smtp')."
    )


def get_email_provider() -> EmailProvider:
    """Lazily constructs and caches a single provider instance for the
    process, built on first real use (the first invitation sent), not at
    app-boot time -- so a deployment that never sends mail still starts,
    and a misconfigured one fails clearly and immediately the first time
    mail is actually needed.
    """
    global _provider
    if _provider is None:
        _provider = _build_provider()
    return _provider


def reset_email_provider_cache() -> None:
    """Test/operator-tooling only: forces the next get_email_provider()
    call to rebuild from current settings rather than reuse a cached
    instance.
    """
    global _provider
    _provider = None
