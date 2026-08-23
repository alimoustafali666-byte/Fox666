import uuid
from datetime import date, datetime

from pydantic import BaseModel


class BriefItemPublic(BaseModel):
    id: uuid.UUID
    category: str
    text: str
    priority: int
    source_document_id: uuid.UUID | None


class DailyBriefPublic(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    generated_by: uuid.UUID
    brief_date: date
    summary: str
    generated_at: datetime
    items: list[BriefItemPublic]


class DailyBriefSummary(BaseModel):
    """List-view row -- no items, matching how every other paginated list
    endpoint in this API (documents, conversations) returns summaries,
    not full nested detail.
    """

    id: uuid.UUID
    company_id: uuid.UUID
    generated_by: uuid.UUID
    brief_date: date
    summary: str
    generated_at: datetime


class DailyBriefPage(BaseModel):
    items: list[DailyBriefSummary]
    next_cursor: str | None

