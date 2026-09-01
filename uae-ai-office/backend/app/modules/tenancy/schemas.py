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
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)


class InvitationPublic(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime


class InvitationCreateResponse(InvitationPublic):
    token: str

