import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, EmailStr, Field


class CompanyPublic(BaseModel):
    id: uuid.UUID
    name: str
    timezone: str
    country: str
    has_logo: bool


class CurrentCompanyResponse(BaseModel):
    company: CompanyPublic
    role: str


class DailyBriefSchedulePublic(BaseModel):
    enabled: bool
    time: time
    timezone: str
    last_scheduled_date: date | None


class DailyBriefScheduleUpdateRequest(BaseModel):
    enabled: bool
    time: time


class CompanyMemberPublic(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    created_at: datetime


class CompanyUpdateRequest(BaseModel):
    """All fields optional -- a PATCH only touches what it sends. Empty
    strings are rejected (min_length=1): a company always has a name,
    timezone, and country, never a blanked-out one.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    timezone: str | None = Field(default=None, min_length=1, max_length=100)
    country: str | None = Field(default=None, min_length=2, max_length=2)


class MemberRoleUpdateRequest(BaseModel):
    # Validated against tenancy.roles.ROLE_HIERARCHY in the service layer
    # (same convention as every other enum-like field in this app --
    # tasks.status, projects.status -- validate in service, not via a
    # Pydantic Literal, so the single source of truth stays one place).
    role: str


class InvitationCreateRequest(BaseModel):
    email: EmailStr
    role: str


class InvitationAcceptRequest(BaseModel):
    """`password` means one of two different things depending on whether
    the invited address already has an account -- the password to create,
    or the existing account's password to authenticate with. The client
    learns which from InvitationPreviewResponse.requires_existing_password.

    `full_name` is optional because it only applies to the create case;
    an invitation is never allowed to rewrite an existing user's profile,
    so anything sent alongside an existing account is ignored. The
    service still requires it when it is actually creating the user.
    """

    password: str = Field(min_length=12, max_length=128)
    full_name: str | None = Field(default=None, min_length=1, max_length=200)


class InvitationPreviewResponse(BaseModel):
    """What an unauthenticated visitor holding an invitation link is told
    before accepting: enough to recognise the invitation as genuine, and
    nothing that would leak company internals to someone who guessed a
    token.

    `requires_existing_password` is the important field. When the invited
    address already has an account, accepting means joining a company
    with that account, and the accept endpoint demands that account's
    existing password. The form has to ask for the right thing, so the
    distinction is exposed here rather than discovered through a failed
    submission.
    """

    email: str
    company_name: str
    role: str
    expires_at: datetime
    requires_existing_password: bool


class InvitationPublic(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime


class InvitationEmailDeliveryPublic(BaseModel):
    """Whether the invitation email actually went out.

    Carried in the response body rather than expressed as an HTTP error
    so that an unconfigured mailer cannot destroy an otherwise valid
    invitation: the client still receives a working `invite_url` it can
    share by hand, and still knows -- exactly -- that nothing was
    emailed. `status` is "sent", "not_configured" or "failed"; only
    "sent" means a provider accepted the message.
    """

    status: str
    detail: str | None = None
    provider: str | None = None


class InvitationCreateResponse(InvitationPublic):
    token: str
    # The absolute accept link. Always present and always usable,
    # whether or not the email went out -- this is what makes the
    # invitation feature work before email credentials are configured.
    invite_url: str
    email_delivery: InvitationEmailDeliveryPublic

