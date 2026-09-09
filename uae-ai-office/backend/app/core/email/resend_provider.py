"""Resend provider -- the transactional email HTTP API at
https://api.resend.com/emails.

Called over plain HTTP with httpx (already a project dependency) rather
than via a vendor SDK, the same deliberate choice made for Voyage AI in
Step 10: a single JSON POST does not justify another dependency.

Credential handling: RESEND_API_KEY is sent only as a Bearer
Authorization header. It is never logged, never placed in an exception
message, and no vendor response body is re-raised verbatim -- each
failure is mapped onto one of this package's typed exceptions with a
fixed message, with the provider's own `message` field appended only
when it is a short, non-sensitive validation string.
"""

import httpx

from app.core.email.exceptions import (
    EmailAuthenticationError,
    EmailOperationError,
    EmailRecipientRejectedError,
    EmailUnavailable,
)
from app.core.email.provider import EmailMessage, EmailProvider, EmailSendResult

_API_URL = "https://api.resend.com/emails"


class ResendEmailProvider(EmailProvider):
    name = "resend"

    def __init__(
        self,
        *,
        api_key: str,
        from_address: str,
        from_name: str | None,
        reply_to: str | None,
        timeout_seconds: float,
    ) -> None:
        self._api_key = api_key
        self._from_address = from_address
        self._from_name = from_name
        self._reply_to = reply_to
        self._timeout_seconds = timeout_seconds

    @property
    def _from_header(self) -> str:
        if self._from_name:
            return f"{self._from_name} <{self._from_address}>"
        return self._from_address

    def send(self, message: EmailMessage) -> EmailSendResult:
        payload: dict[str, object] = {
            "from": self._from_header,
            "to": [message.to_address],
            "subject": message.subject,
            "html": message.html_body,
            "text": message.text_body,
        }
        if self._reply_to:
            payload["reply_to"] = self._reply_to

        try:
            response = httpx.post(
                _API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise EmailUnavailable("The email provider did not respond in time.") from exc
        except httpx.HTTPError as exc:
            raise EmailUnavailable("Could not reach the email provider.") from exc

        if response.status_code in (401, 403):
            raise EmailAuthenticationError(
                "The email provider rejected the configured API key."
            )
        if response.status_code == 429:
            raise EmailUnavailable("The email provider is rate limiting this sender.")
        if response.status_code >= 500:
            raise EmailUnavailable("The email provider reported a server error.")
        if response.status_code in (400, 422):
            raise EmailRecipientRejectedError(
                "The email provider rejected the message: " + _safe_reason(response)
            )
        if response.status_code >= 400:
            raise EmailOperationError(
                "The email provider refused the message: " + _safe_reason(response)
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise EmailOperationError(
                "The email provider returned a response that could not be parsed."
            ) from exc

        message_id = body.get("id") if isinstance(body, dict) else None
        if not message_id:
            # No id means the provider did not confirm it took the
            # message -- never report that as accepted.
            raise EmailOperationError(
                "The email provider did not return a message id for this send."
            )
        return EmailSendResult(provider=self.name, provider_message_id=str(message_id))


def _safe_reason(response: httpx.Response) -> str:
    """Resend's 4xx bodies are short, operator-facing validation strings
    ("The from address is not verified", "Invalid `to` field"). Only that
    one field is surfaced, truncated, and only for the client-error
    statuses where it is actionable -- never the whole body, and never
    for any status where the body might echo request content back.
    """
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code}."
    reason = body.get("message") if isinstance(body, dict) else None
    if not isinstance(reason, str) or not reason.strip():
        return f"HTTP {response.status_code}."
    return reason.strip()[:200]
