import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CompanyPublic(BaseModel):
    id: uuid.UUID
    name: str
    timezone: str
    country: str
    has_logo: bool


class CurrentCompanyResponse(BaseModel):
    company: CompanyPublic
    role: str


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

