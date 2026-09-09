"""The abstraction every module that needs to send mail depends on.
Business/domain code (app.modules.tenancy, for team invitations) must
never import smtplib, httpx-against-a-mail-API, or a vendor SDK
directly -- only this interface and the factory that resolves it from
configuration (app.core.email.factory.get_email_provider).

There is deliberately NO "fake"/console provider here, unlike the
storage/LLM/embedding abstractions. Those have one because a fake is a
useful stand-in for a *read* path in tests. Mail is a side effect on the
outside world: a provider that silently accepts a message and drops it
would let a deployment report "invitation sent" while nothing was ever
delivered, which is exactly the failure this module exists to prevent.

An unconfigured deployment therefore gets no provider at all -- the
factory raises EmailConfigurationError rather than inventing one. What
callers do with that is theirs to decide: the team-invitation flow, for
instance, catches it and reports email_delivery.status =
"not_configured" alongside a still-usable invitation link, so the
feature works before mail credentials exist without ever claiming a
message was sent.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class EmailMessage:
    """One transactional message. `text_body` is mandatory, not optional:
    a multipart/alternative message with a real plaintext part is what
    keeps the mail out of spam filters that penalise HTML-only mail, and
    is what plain-text clients actually show.
    """

    to_address: str
    subject: str
    html_body: str
    text_body: str
    to_name: str | None = None


@dataclass(frozen=True)
class EmailSendResult:
    """What the provider said when it took responsibility for the
    message. `provider_message_id` is the identifier the operator can
    look up in the provider's own delivery log -- the evidence that the
    provider accepted it, as opposed to this application merely having
    tried. `accepted` is never True unless the provider said so.
    """

    provider: str
    provider_message_id: str
    accepted: bool = True


class EmailProvider(ABC):
    #: Short, stable name used in logs and in the accepted-for-delivery
    #: record so an operator knows which provider's log to check.
    name: str = "email"

    @abstractmethod
    def send(self, message: EmailMessage) -> EmailSendResult:
        """Hands `message` to the provider and returns only once the
        provider has accepted it for delivery. Raises an
        app.core.email.exceptions.EmailError subclass otherwise -- this
        method never returns normally for a message that was not
        accepted, and never swallows a failure.

        "Accepted for delivery" is the strongest guarantee any mail
        provider offers synchronously; final delivery to the recipient's
        mailbox is asynchronous and observable only in the provider's
        own delivery log or via webhooks.
        """
