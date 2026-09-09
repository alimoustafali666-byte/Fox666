"""SMTP provider -- works against any SMTP relay (Amazon SES SMTP,
SendGrid, Mailgun, Postmark, Resend's SMTP endpoint, or a corporate
Exchange/Microsoft 365 relay).

Uses the standard library's smtplib/email packages rather than adding a
dependency: SMTP submission is a stable, fully-specified protocol and
stdlib covers it, in the same spirit as Step 10's deliberate choice to
call Voyage over plain HTTP instead of pulling in an SDK.

Credential handling: SMTP_PASSWORD is passed to smtplib.login() and is
never logged, never included in an exception message, and never echoed
back to a caller. smtplib's own exception objects carry the *server's*
reply text (which does not contain the password) -- even so, nothing
here re-raises a vendor string verbatim; each failure is mapped onto one
of this package's typed exceptions with a fixed message, and the
original is chained via `from exc` for server-side debugging only.
"""

import smtplib
import ssl
from email.message import EmailMessage as MIMEEmailMessage
from email.utils import formataddr, make_msgid

from app.core.email.exceptions import (
    EmailAuthenticationError,
    EmailOperationError,
    EmailRecipientRejectedError,
    EmailUnavailable,
)
from app.core.email.provider import EmailMessage, EmailProvider, EmailSendResult


class SmtpEmailProvider(EmailProvider):
    name = "smtp"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        from_address: str,
        from_name: str | None,
        reply_to: str | None,
        use_starttls: bool,
        use_ssl: bool,
        timeout_seconds: float,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_address = from_address
        self._from_name = from_name
        self._reply_to = reply_to
        self._use_starttls = use_starttls
        self._use_ssl = use_ssl
        self._timeout_seconds = timeout_seconds

    def _build_mime(self, message: EmailMessage) -> tuple[MIMEEmailMessage, str]:
        mime = MIMEEmailMessage()
        mime["From"] = formataddr((self._from_name, self._from_address))
        mime["To"] = formataddr((message.to_name, message.to_address))
        mime["Subject"] = message.subject
        if self._reply_to:
            mime["Reply-To"] = self._reply_to
        # Generated here (rather than left to the relay) so the value we
        # report back as the provider message id is the same one that
        # appears in the relay's log and in the delivered message.
        message_id = make_msgid(domain=self._from_address.rsplit("@", 1)[-1])
        mime["Message-ID"] = message_id
        # Plaintext first, HTML as the richer alternative -- the order
        # multipart/alternative requires.
        mime.set_content(message.text_body)
        mime.add_alternative(message.html_body, subtype="html")
        return mime, message_id

    def _connect(self) -> smtplib.SMTP:
        context = ssl.create_default_context()
        if self._use_ssl:
            return smtplib.SMTP_SSL(
                self._host, self._port, timeout=self._timeout_seconds, context=context
            )
        client = smtplib.SMTP(self._host, self._port, timeout=self._timeout_seconds)
        if self._use_starttls:
            client.starttls(context=context)
        return client

    def send(self, message: EmailMessage) -> EmailSendResult:
        mime, message_id = self._build_mime(message)
        try:
            with self._connect() as client:
                client.ehlo()
                if self._username and self._password:
                    client.login(self._username, self._password)
                refused = client.send_message(mime)
        except smtplib.SMTPAuthenticationError as exc:
            raise EmailAuthenticationError(
                "The SMTP server rejected the configured credentials."
            ) from exc
        except (smtplib.SMTPSenderRefused, smtplib.SMTPRecipientsRefused) as exc:
            raise EmailRecipientRejectedError(
                "The SMTP server refused the sender or the recipient address."
            ) from exc
        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, TimeoutError, OSError) as exc:
            raise EmailUnavailable("Could not reach the configured SMTP server.") from exc
        except smtplib.SMTPException as exc:
            raise EmailOperationError("The SMTP server refused the message.") from exc

        if refused:
            # send_message returns a per-recipient refusal map; a
            # non-empty map for our single recipient means nothing was
            # accepted, so this must not be reported as a success.
            raise EmailRecipientRejectedError(
                "The SMTP server refused the recipient address."
            )
        return EmailSendResult(provider=self.name, provider_message_id=message_id)
