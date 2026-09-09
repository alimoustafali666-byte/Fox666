"""Company administration: company info edit, logo upload/download/
delete, member role change, member removal. All state-changing actions
here are gated by the router's require_roles("owner", "admin") -- this
module additionally enforces the finer, target-aware rules that a flat
role check can't express (an admin must not be able to touch an owner;
a company must always keep at least one owner), the same "RLS/route role
check is the broad boundary, service layer is the precise one" split
used throughout this app.

Invitations live here too. An invitation is only ever reported as sent
once a real email provider has accepted the message for delivery: the
record is written first (so an operator can retry with Resend), the mail
is handed to app.core.email, and any provider failure is raised as a
typed error the router turns into a non-2xx response. There is no code
path in which this module returns success for an email that was not
accepted by a provider -- see app/core/email/provider.py for why no
fake/console provider exists.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email.exceptions import EmailConfigurationError, EmailError
from app.core.email.factory import get_email_provider
from app.core.security import (
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password_or_dummy,
)
from app.core.storage.exceptions import ObjectNotFoundError, StorageError
from app.core.storage.factory import get_storage_provider
from app.core.storage.keys import build_company_logo_object_key
from app.core.storage.provider import StorageProvider
from app.db.session import set_company_context, set_user_context
from app.modules.audit_log.service import record_audit_event
from app.modules.auth import repository as auth_repository
from app.modules.documents.content_validation import detect_and_validate_content_type
from app.modules.documents.exceptions import FileTooLargeError, UnsupportedFileTypeError
from app.modules.documents.upload_stream import measure_and_checksum
from app.modules.tenancy import repository
from app.modules.tenancy.exceptions import (
    CannotRemoveSelfError,
    InsufficientRoleForActionError,
    InvalidRoleError,
    InvitationAlreadyExistsError,
    InvitationExistingAccountError,
    InvitationInvalidError,
    InvitationNotFoundError,
    LastOwnerError,
    LogoNotFoundError,
    LogoStorageUnavailableError,
    LogoTooLargeError,
    MemberNotFoundError,
    UnsupportedLogoTypeError,
)
from app.modules.tenancy.invitation_email import build_invitation_email
from app.modules.tenancy.models import Company, CompanyInvitation, CompanyMember
from app.modules.tenancy.roles import ROLE_HIERARCHY

logger = logging.getLogger(__name__)

_ALLOWED_LOGO_MIME_TYPES = {"image/png", "image/jpeg"}
_MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2 MiB -- a logo, not a document
def _invitation_ttl() -> timedelta:
    """Read at call time, not import time, so the configured value is
    honoured without a code change (and so tests can vary it).
    """
    return timedelta(days=settings.invitation_ttl_days)


def _compensate_storage_delete(provider: StorageProvider, storage_key: str) -> None:
    try:
        provider.delete(key=storage_key)
    except StorageError:
        logger.exception(
            "Compensating delete failed after a failed logo upload; an "
            "orphaned storage object may exist at key=%s",
            storage_key,
        )


def update_company(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    name: str | None,
    timezone: str | None,
    country: str | None,
    ip_address: str | None,
) -> Company:
    company = repository.update_company(
        db, company_id=company_id, name=name, timezone=timezone, country=country
    )
    record_audit_event(
        db,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="tenancy.company_updated",
        resource_type="company",
        resource_id=company_id,
        metadata={"name": name, "timezone": timezone, "country": country},
        ip_address=ip_address,
    )
    db.commit()
    return company


def upload_company_logo(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    upload_file,  # fastapi.UploadFile-shaped: .filename (str), .file (BinaryIO)
    ip_address: str | None,
) -> Company:
    fileobj: BinaryIO = upload_file.file
    try:
        size_bytes, _checksum = measure_and_checksum(fileobj, max_bytes=_MAX_LOGO_BYTES)
    except FileTooLargeError as exc:
        raise LogoTooLargeError(
            f"Logo exceeds the maximum allowed size of {_MAX_LOGO_BYTES} bytes."
        ) from exc

    try:
        content_type = detect_and_validate_content_type(
            filename=upload_file.filename or "logo.png", fileobj=fileobj
        )
    except UnsupportedFileTypeError as exc:
        raise UnsupportedLogoTypeError("Logo must be a PNG or JPEG image.") from exc
    if content_type not in _ALLOWED_LOGO_MIME_TYPES:
        raise UnsupportedLogoTypeError("Logo must be a PNG or JPEG image.")

    extension = "png" if content_type == "image/png" else "jpg"
    storage_key = build_company_logo_object_key(company_id=company_id, object_name=f"logo.{extension}")

    provider = get_storage_provider()
    try:
        fileobj.seek(0)
        provider.upload(key=storage_key, data=fileobj, content_type=content_type)
    except StorageError as exc:
        raise LogoStorageUnavailableError("Unable to store the logo right now.") from exc

    old_company = db.get(Company, company_id)
    old_key = old_company.logo_storage_key if old_company else None

    try:
        company = repository.set_company_logo(
            db, company_id=company_id, storage_key=storage_key, content_type=content_type
        )
        record_audit_event(
            db,
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="tenancy.logo_uploaded",
            resource_type="company",
            resource_id=company_id,
            metadata={"content_type": content_type, "size_bytes": size_bytes},
            ip_address=ip_address,
        )
        db.commit()
    except Exception:
        db.rollback()
        _compensate_storage_delete(provider, storage_key)
        raise

    if old_key and old_key != storage_key:
        _compensate_storage_delete(provider, old_key)

    return company


def delete_company_logo(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, ip_address: str | None
) -> Company:
    company = db.get(Company, company_id)
    old_key = company.logo_storage_key if company else None

    company = repository.set_company_logo(db, company_id=company_id, storage_key=None, content_type=None)
    record_audit_event(
        db,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="tenancy.logo_deleted",
        resource_type="company",
        resource_id=company_id,
        metadata={},
        ip_address=ip_address,
    )
    db.commit()

    if old_key:
        _compensate_storage_delete(get_storage_provider(), old_key)

    return company


def get_company_logo_bytes(db: Session, *, company_id: uuid.UUID) -> tuple[bytes, str]:
    company = db.get(Company, company_id)
    if company is None or not company.logo_storage_key:
        raise LogoNotFoundError("This company has no logo set.")

    provider = get_storage_provider()
    try:
        data = provider.download(key=company.logo_storage_key)
    except ObjectNotFoundError as exc:
        raise LogoNotFoundError("This company has no logo set.") from exc
    return data, company.logo_content_type or "application/octet-stream"


def change_member_role(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: str,
    target_user_id: uuid.UUID,
    new_role: str,
    ip_address: str | None,
) -> CompanyMember:
    if new_role not in ROLE_HIERARCHY:
        raise InvalidRoleError(f"role must be one of {list(ROLE_HIERARCHY)}.")

    member = auth_repository.get_membership(db, target_user_id, company_id)
    if member is None:
        raise MemberNotFoundError("This member could not be found.")

    # Only an owner may touch an owner-level member -- granting OR
    # revoking owner status, or changing an existing owner's role to
    # anything else -- an admin can manage manager/member/admin-level
    # members but never an owner. Prevents an admin from unilaterally
    # demoting/removing every owner or promoting themselves to one.
    if (member.role == "owner" or new_role == "owner") and actor_role != "owner":
        raise InsufficientRoleForActionError(
            "Only an owner can change another owner's role or grant owner access."
        )

    if member.role == "owner" and new_role != "owner":
        owner_count = repository.count_members_by_role(db, company_id=company_id, role="owner")
        if owner_count <= 1:
            raise LastOwnerError("A company must always have at least one owner.")

    old_role = member.role
    member = repository.update_member_role(db, member=member, role=new_role)
    record_audit_event(
        db,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="tenancy.member_role_changed",
        resource_type="company_member",
        resource_id=member.id,
        metadata={"target_user_id": str(target_user_id), "old_role": old_role, "new_role": new_role},
        ip_address=ip_address,
    )
    db.commit()
    return member


def remove_member(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: str,
    target_user_id: uuid.UUID,
    ip_address: str | None,
) -> None:
    if target_user_id == actor_user_id:
        raise CannotRemoveSelfError("You cannot remove yourself from the company.")

    member = auth_repository.get_membership(db, target_user_id, company_id)
    if member is None:
        raise MemberNotFoundError("This member could not be found.")

    if member.role == "owner":
        if actor_role != "owner":
            raise InsufficientRoleForActionError("Only an owner can remove another owner.")
        owner_count = repository.count_members_by_role(db, company_id=company_id, role="owner")
        if owner_count <= 1:
            raise LastOwnerError("A company must always have at least one owner.")

    removed_role = member.role
    repository.delete_member(db, member=member)
    record_audit_event(
        db,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="tenancy.member_removed",
        resource_type="company_member",
        resource_id=None,
        metadata={"target_user_id": str(target_user_id), "role": removed_role},
        ip_address=ip_address,
    )
    db.commit()


def invitation_status(invitation: CompanyInvitation, now: datetime | None = None) -> str:
    if invitation.revoked_at is not None:
        return "revoked"
    if invitation.accepted_at is not None:
        return "accepted"
    if invitation.expires_at <= (now or datetime.now(UTC)):
        return "expired"
    return "pending"


def _ensure_invitation_role(role: str) -> None:
    if role not in ROLE_HIERARCHY:
        raise InvalidRoleError(f"role must be one of {list(ROLE_HIERARCHY)}.")
    if role == "owner":
        raise InsufficientRoleForActionError("Invitations cannot grant owner access.")


@dataclass(frozen=True)
class InvitationDelivery:
    """What actually happened to the invitation email, reported back to
    the caller instead of being raised.

    The original design raised a 5xx when no provider was configured.
    That kept the "never claim sent when it wasn't" guarantee but threw
    away the usable invitation with it: the record existed, the token
    existed, and the operator had no way to reach either. Reporting the
    outcome as data keeps the same guarantee -- the UI renders "sent"
    only for status="sent" -- while leaving the operator a working
    invitation link they can share by hand until mail is configured.

    status:
      "sent"           -- a provider accepted the message for delivery.
      "not_configured" -- no usable EMAIL_PROVIDER; nothing was sent.
      "failed"         -- a provider was configured and refused the
                          message (bad credential, unverified sending
                          domain, rejected recipient, outage).
    """

    status: str
    detail: str | None = None
    provider: str | None = None
    provider_message_id: str | None = None


def _deliver_invitation_email(
    db: Session,
    *,
    invitation: CompanyInvitation,
    raw_token: str,
    actor_user_id: uuid.UUID,
    action: str,
    ip_address: str | None,
) -> InvitationDelivery:
    """Hands the invitation to the configured email provider, records
    what the provider said, and returns that outcome.

    Nothing here reports a send that did not happen: a message is only
    ever described as "sent" once a provider has accepted it, and the
    audit event carries the same status plus the provider's own message
    id, so "did this actually go out?" stays answerable from the audit
    log and cross-checkable against the provider's delivery log.
    """
    company = db.get(Company, invitation.company_id)
    inviter = auth_repository.get_user_by_id(db, invitation.invited_by)

    delivery: InvitationDelivery
    try:
        message = build_invitation_email(
            invitee_email=str(invitation.email),
            company_name=company.name if company else "your company",
            inviter_name=inviter.full_name if inviter else None,
            role=invitation.role,
            raw_token=raw_token,
            expires_at=invitation.expires_at,
        )
        provider = get_email_provider()
        result = provider.send(message)
    except EmailConfigurationError as exc:
        logger.warning(
            "Invitation email for invitation_id=%s was not sent: email delivery "
            "is not configured (%s). The invitation link is still valid and can "
            "be shared manually.",
            invitation.id,
            exc,
        )
        delivery = InvitationDelivery(status="not_configured", detail=str(exc))
    except EmailError as exc:
        logger.error(
            "Invitation email for invitation_id=%s was refused by the email "
            "provider (%s): %s",
            invitation.id,
            exc.error_code,
            exc,
        )
        delivery = InvitationDelivery(status="failed", detail=str(exc))
    else:
        delivery = InvitationDelivery(
            status="sent",
            provider=result.provider,
            provider_message_id=result.provider_message_id,
        )
        logger.info(
            "Invitation email accepted for delivery: invitation_id=%s provider=%s "
            "provider_message_id=%s",
            invitation.id,
            result.provider,
            result.provider_message_id,
        )

    record_audit_event(
        db,
        company_id=invitation.company_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type="company_invitation",
        resource_id=invitation.id,
        metadata={
            "email": str(invitation.email),
            "role": invitation.role,
            "email_delivery_status": delivery.status,
            "email_provider": delivery.provider,
            "provider_message_id": delivery.provider_message_id,
            "expires_at": invitation.expires_at.isoformat(),
        },
        ip_address=ip_address,
    )
    db.commit()
    return delivery


def create_invitation(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID,
                      email: str, role: str,
                      ip_address: str | None = None,
                      ) -> tuple[CompanyInvitation, str, InvitationDelivery]:
    _ensure_invitation_role(role)
    active = db.execute(select(CompanyInvitation).where(
        CompanyInvitation.company_id == company_id,
        CompanyInvitation.email == email,
        CompanyInvitation.accepted_at.is_(None),
        CompanyInvitation.revoked_at.is_(None),
    )).scalar_one_or_none()
    if active and invitation_status(active) == "pending":
        raise InvitationAlreadyExistsError("A pending invitation already exists for this email.")
    raw_token = generate_refresh_token()
    invitation = repository.create_invitation(
        db, company_id=company_id, email=email, role=role, invited_by=actor_user_id,
        token_hash=hash_refresh_token(raw_token), expires_at=datetime.now(UTC) + _invitation_ttl(),
    )
    # Committed before the send so that a provider failure leaves a
    # pending invitation the operator can retry with Resend, rather than
    # losing the record. The send outcome travels back in the return
    # value, so the caller can tell the operator exactly what happened
    # instead of the UI guessing that mail went out.
    db.commit()
    delivery = _deliver_invitation_email(
        db,
        invitation=invitation,
        raw_token=raw_token,
        actor_user_id=actor_user_id,
        action="tenancy.invitation_sent",
        ip_address=ip_address,
    )
    return invitation, raw_token, delivery


def list_company_invitations(db: Session, company_id: uuid.UUID) -> list[CompanyInvitation]:
    return repository.list_invitations(db, company_id)


def resend_invitation(db: Session, *, company_id: uuid.UUID, invitation_id: uuid.UUID,
                     actor_user_id: uuid.UUID,
                     ip_address: str | None = None,
                     ) -> tuple[CompanyInvitation, str, InvitationDelivery]:
    """Issues a fresh token, extends the expiry, and sends a new email.

    The old token stops working the moment this commits (token_hash is
    overwritten), so a resent invitation supersedes the previous one
    rather than leaving two live links. Like create_invitation, the
    email outcome is returned rather than raised -- Resend is also how
    an operator regenerates a shareable link after email configuration
    changes, and that has to keep working while mail is still pending.
    """
    invitation = repository.get_invitation(db, company_id, invitation_id)
    if invitation is None or invitation_status(invitation) != "pending":
        raise InvitationNotFoundError("This pending invitation could not be found.")
    raw_token = generate_refresh_token()
    invitation.token_hash = hash_refresh_token(raw_token)
    invitation.expires_at = datetime.now(UTC) + _invitation_ttl()
    db.commit()
    delivery = _deliver_invitation_email(
        db,
        invitation=invitation,
        raw_token=raw_token,
        actor_user_id=actor_user_id,
        action="tenancy.invitation_resent",
        ip_address=ip_address,
    )
    return invitation, raw_token, delivery


def revoke_invitation(db: Session, *, company_id: uuid.UUID, invitation_id: uuid.UUID) -> None:
    invitation = repository.get_invitation(db, company_id, invitation_id)
    if invitation is None or invitation_status(invitation) != "pending":
        raise InvitationNotFoundError("This pending invitation could not be found.")
    invitation.revoked_at = datetime.now(UTC)
    db.commit()


def get_invitation_for_acceptance(db: Session, raw_token: str) -> CompanyInvitation:
    invitation = repository.get_invitation_by_token_hash(db, hash_refresh_token(raw_token))
    if invitation is None or invitation_status(invitation) != "pending":
        raise InvitationInvalidError("This invitation is no longer valid.")
    return invitation


def invitation_requires_existing_password(db: Session, invitation: CompanyInvitation) -> bool:
    """True when the invited address already has an account, so accepting
    means "add my existing account to this company" rather than "create
    my account". The accept form asks for a different password in each
    case, so the client needs to know which before rendering it.
    """
    return auth_repository.get_user_by_email(db, str(invitation.email)) is not None


def accept_invitation(db: Session, *, raw_token: str, email: str, password: str,
                      full_name: str | None) -> tuple[object, str]:
    from app.modules.auth import service as auth_service

    invitation = get_invitation_for_acceptance(db, raw_token)
    if invitation.email.lower() != email.lower():
        raise InvitationInvalidError("This invitation is for a different email address.")
    user = auth_repository.get_user_by_email(db, email)
    if user is None:
        if not (full_name and full_name.strip()):
            raise InvitationInvalidError("Your full name is required to create your account.")
        user = auth_repository.create_user(
            db, email=email, password_hash=hash_password(password), full_name=full_name.strip()
        )
    else:
        # The address already has an account, so this call is about to
        # hand out a session for a user who existed before the
        # invitation did. The token alone cannot authorise that: any
        # owner/admin can invite an arbitrary address and reads the raw
        # token directly from the create-invitation response, so an
        # unchecked accept here would be an account takeover -- and,
        # through /auth/me/companies/switch, a way into every other
        # company that account belongs to. The existing account must
        # therefore authenticate as itself.
        #
        # verify_password_or_dummy keeps the timing indistinguishable
        # from the create branch, and full_name is deliberately ignored:
        # an invitation must not be able to rewrite an existing user's
        # profile.
        if not verify_password_or_dummy(password, user.password_hash):
            raise InvitationExistingAccountError(
                "An account already exists for this email address. Enter that "
                "account's existing password to join this company."
            )
    set_company_context(db, invitation.company_id)
    if auth_repository.get_membership(db, user.id, invitation.company_id) is None:
        auth_repository.create_company_member(
            db, company_id=invitation.company_id, user_id=user.id, role=invitation.role
        )
    invitation.accepted_at = datetime.now(UTC)
    set_user_context(db, user.id)
    access_token_response = auth_service._access_token_response(
        user_id=user.id, company_id=invitation.company_id, role=invitation.role
    )
    raw_refresh_token, _ = auth_service._issue_refresh_session(
        db, user_id=user.id, company_id=invitation.company_id, family_id=uuid.uuid4()
    )
    db.commit()
    return access_token_response, raw_refresh_token

