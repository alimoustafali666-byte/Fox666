from datetime import datetime

from pydantic import BaseModel


class ReportTypeInfo(BaseModel):
    type: str
    title_en: str
    title_ar: str


class ReportColumnPublic(BaseModel):
    key: str
    label: str


class ReportPreviewMeta(BaseModel):
    report_type: str
    title: str
    company_name: str
    generated_at: datetime
    generated_by: str
    reference_number: str
    filters_summary: str
    row_count: int


class ReportPreviewResponse(BaseModel):
    meta: ReportPreviewMeta
    columns: list[ReportColumnPublic]
    rows: list[dict[str, str]]


class BriefSummary(BaseModel):
    brief_date: str
    item_count: int
    summary: str


class RecentActivityEntry(BaseModel):
    created_at: str
    actor: str
    action: str
    resource_type: str


class DashboardSummaryResponse(BaseModel):
    project_status_counts: dict[str, int]
    document_status_counts: dict[str, int]
    my_tasks: dict[str, int]
    company_tasks: dict[str, int] | None
    latest_brief: BriefSummary | None
    my_ticket_status_counts: dict[str, int]
    unread_notifications: int
    recent_activity: list[RecentActivityEntry] | None

