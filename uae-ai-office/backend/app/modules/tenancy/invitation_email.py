"""Builds the team-invitation email: the accept URL, the subject, and
the HTML/plaintext bodies.

Kept separate from service.py (which owns the invitation lifecycle) and
from app.core.email (which owns transport) so that "what the message
says" has one home. This module never sends anything and never touches
the database.

Two things here matter beyond presentation:

* The accept URL is built from settings.public_frontend_url, NOT from a
  request's Host header and not from the CORS allowlist (which contains
  localhost entries that are correct for CORS and useless in an inbox).
  See Settings.public_frontend_url for the resolution order.

* Every value interpolated into the HTML is escaped. The company name
  and the inviter's display name are user-supplied strings; unescaped,
  they would inject markup into an email this application sends out
  under its own sending domain.
"""

import logging
from datetime import datetime
from html import escape
from urllib.parse import quote

from app.core.config import settings
from app.core.email.provider import EmailMessage

logger = logging.getLogger(__name__)

_ROLE_LABELS = {
    "owner": "Owner",
    "admin": "Administrator",
    "manager": "Manager",
    "member": "Member",
}


def build_invitation_url(raw_token: str) -> str:
    """The absolute link that lands on the frontend's invitation-accept
    page (frontend route: /invite/[token]).
    """
    base = settings.public_frontend_url
    if not settings.is_public_frontend_url:
        # Not fatal -- a purely local development run is a legitimate
        # case -- but it is always wrong for a real recipient, so it is
        # recorded loudly instead of quietly producing a dead link.
        logger.warning(
            "Invitation links are being built against a loopback URL (%s). "
            "Set APP_PUBLIC_URL to the publicly reachable frontend URL, or "
            "the recipient's link will not work.",
            base,
        )
    return f"{base}/invite/{quote(raw_token, safe='')}"


def _role_label(role: str) -> str:
    return _ROLE_LABELS.get(role, role.capitalize())


def build_invitation_email(
    *,
    invitee_email: str,
    company_name: str,
    inviter_name: str | None,
    role: str,
    raw_token: str,
    expires_at: datetime,
) -> EmailMessage:
    accept_url = build_invitation_url(raw_token)
    role_label = _role_label(role)
    expiry_text = expires_at.strftime("%d %B %Y, %H:%M UTC")
    invited_by = inviter_name.strip() if inviter_name and inviter_name.strip() else None

    subject = f"You have been invited to {company_name} on UAE AI Office"

    intro = (
        f"{invited_by} has invited you"
        if invited_by
        else "You have been invited"
    )

    text_body = f"""{intro} to join {company_name} on UAE AI Office as a {role_label}.

Accept the invitation and set up your account here:
{accept_url}

This link expires on {expiry_text}. If it expires, ask a company owner or
administrator to resend the invitation.

If you were not expecting this invitation you can safely ignore this email --
no account is created until the link above is used.

UAE AI Office
"""

    e_company = escape(company_name)
    e_role = escape(role_label)
    e_intro = escape(intro)
    e_expiry = escape(expiry_text)
    e_url = escape(accept_url, quote=True)

    html_body = f"""<!doctype html>
<html lang="en">
  <body style="margin:0;padding:0;background:#070b18;font-family:'Segoe UI',Helvetica,Arial,sans-serif;color:#e8ecf8;">
    <div style="max-width:560px;margin:0 auto;padding:32px 20px;">
      <div style="font-size:13px;letter-spacing:.18em;text-transform:uppercase;color:#35d9f2;font-weight:600;">
        UAE AI Office
      </div>
      <div style="margin-top:20px;background:#0d1428;border:1px solid #1e2a4a;border-radius:16px;padding:32px;">
        <h1 style="margin:0 0 16px;font-size:22px;line-height:1.3;color:#ffffff;font-weight:600;">
          You have been invited to {e_company}
        </h1>
        <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#b6c1de;">
          {e_intro} to join <strong style="color:#ffffff;">{e_company}</strong> on UAE AI Office
          as a <strong style="color:#ffffff;">{e_role}</strong>.
        </p>
        <p style="margin:0 0 28px;font-size:15px;line-height:1.6;color:#b6c1de;">
          Use the button below to set your name and password and activate your account.
        </p>
        <p style="margin:0 0 28px;">
          <a href="{e_url}"
             style="display:inline-block;padding:14px 28px;border-radius:10px;background:#4d8dff;color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;">
            Accept invitation
          </a>
        </p>
        <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#8592b4;">
          Or paste this link into your browser:
        </p>
        <p style="margin:0 0 24px;font-size:13px;line-height:1.6;word-break:break-all;">
          <a href="{e_url}" style="color:#35d9f2;text-decoration:none;">{e_url}</a>
        </p>
        <p style="margin:0;font-size:13px;line-height:1.6;color:#8592b4;border-top:1px solid #1e2a4a;padding-top:20px;">
          This invitation expires on {e_expiry}. If it expires, ask a company owner or
          administrator to resend it. If you were not expecting this invitation you can
          safely ignore this email &mdash; no account is created until the link is used.
        </p>
      </div>
      <p style="margin:20px 0 0;font-size:12px;color:#5d6a8c;text-align:center;">
        UAE AI Office
      </p>
    </div>
  </body>
</html>"""

    return EmailMessage(
        to_address=invitee_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )
