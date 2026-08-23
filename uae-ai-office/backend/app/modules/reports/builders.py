"""One data-assembly function per report domain. Every function here
calls the SAME service/repository functions the rest of the app already
uses for that domain's normal list views -- report data is therefore
subject to exactly the RLS/RBAC scoping already proven for those
surfaces, never a parallel or broader query. Nothing here bypasses
tenant isolation: company_id always comes from the caller's own
TenantContext (resolved server-side from the JWT), never a request
parameter.

A report is capped at _MAX_REPORT_ROWS rows fetched in a single call
(each domain's list function has no internal limit ceiling of its own --
only the public HTTP list endpoints cap `limit` via their own Query
validation) rather than looping cursor pages internally. This keeps
report generation time bounded and avoids re-deriving each domain's own
cursor-field convention here; a company with more rows than the cap in
a single filtered view is a real (documented) limitation of this first
reporting pass, not a silent truncation -- row_count in the report
metadata always reflects exactly what's included.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit_log import repository as audit_log_repository
from app.modules.auth import repository as auth_repository
from app.modules.briefs import repository as briefs_repository
from app.modules.collaboration import service as collaboration_service
from app.modules.documents import service as documents_service
from app.modules.projects import service as projects_service
from app.modules.projects.models import Project
from app.modules.reports.rendering import ReportColumn, ReportData, ReportMeta
from app.modules.support import service as support_service
from app.modules.tasks import repository as tasks_repository

_MAX_REPORT_ROWS = 500
_MANAGEMENT_ROLES = ("owner", "admin", "manager")

_STATUS_LABELS_EN = {
    # Projects
    "planning": "Planning", "active": "Active", "on_hold": "On Hold",
    "completed": "Completed", "cancelled": "Cancelled",
    # Documents
    "uploaded": "Uploaded", "processing": "Processing", "processed": "Processed", "failed": "Failed",
    # Tasks
    "todo": "To do", "in_progress": "In Progress", "blocked": "Blocked",
    # Tasks priorities
    "low": "Low", "normal": "Normal", "high": "High", "urgent": "Urgent",
    # Support tickets
    "open": "Open", "waiting_for_user": "Waiting for you", "resolved": "Resolved", "closed": "Closed",
}
_STATUS_LABELS_AR = {
    "planning": "التخطيط", "active": "نشط", "on_hold": "معلّق", "completed": "مكتمل", "cancelled": "ملغى",
    "uploaded": "مرفوع", "processing": "قيد المعالجة", "processed": "تمت المعالجة", "failed": "فشل",
    "todo": "قيد الانتظار", "in_progress": "قيد التنفيذ", "blocked": "معلّقة",
    "low": "منخفضة", "normal": "عادية", "high": "عالية", "urgent": "عاجلة",
    "open": "مفتوحة", "waiting_for_user": "بانتظارك", "resolved": "تم الحل", "closed": "مغلقة",
}


def _label(value: str | None, locale: str) -> str:
    if value is None:
        return ""
    table = _STATUS_LABELS_AR if locale == "ar" else _STATUS_LABELS_EN
    return table.get(value, value)


def _fmt_dt(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


def _fmt_date(value: date | None) -> str:
    return value.isoformat() if value else ""


def _actor_display_name(db: Session, actor_user_id: uuid.UUID) -> str:
    user = auth_repository.get_user_by_id(db, actor_user_id)
    if user is None:
        return "Unknown"
    return user.full_name or user.email


def _project_names_for(db: Session, *, company_id: uuid.UUID, project_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    project_ids.discard(None)
    if not project_ids:
        return {}
    rows = db.execute(
        select(Project.id, Project.name).where(Project.company_id == company_id, Project.id.in_(project_ids))
    ).all()
    return {row[0]: row[1] for row in rows}


def _user_names_for(db: Session, *, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    user_ids.discard(None)
    names: dict[uuid.UUID, str] = {}
    for user_id in user_ids:
        user = auth_repository.get_user_by_id(db, user_id)
        if user is not None:
            names[user_id] = user.full_name or user.email
    return names


# --- Projects ---

_PROJECT_COLUMNS = [
    ReportColumn("name", "Name", "الاسم"),
    ReportColumn("project_code", "Code", "الرمز"),
    ReportColumn("status", "Status", "الحالة"),
    ReportColumn("description", "Description", "الوصف"),
    ReportColumn("created_at", "Created", "تاريخ الإنشاء"),
    ReportColumn("updated_at", "Updated", "آخر تحديث"),
]


def build_projects_report(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, actor_role: str, locale: str, filters: dict
) -> ReportData:
    status = filters.get("status")
    search = filters.get("search")
    projects = projects_service.list_projects(
        db, company_id=company_id, limit=_MAX_REPORT_ROWS, cursor=None,
        status=status, project_code=None, name_search=search,
    )
    rows = [
        {
            "name": p.name,
            "project_code": p.project_code or "",
            "status": _label(p.status, locale),
            "description": p.description or "",
            "created_at": _fmt_dt(p.created_at),
            "updated_at": _fmt_dt(p.updated_at),
        }
        for p in projects
    ]
    parts = []
    if status:
        parts.append(f"Status: {_label(status, 'en')}" if locale != "ar" else f"الحالة: {_label(status, 'ar')}")
    if search:
        parts.append(f"Search: {search}" if locale != "ar" else f"بحث: {search}")
    summary = " | ".join(parts)
    return ReportData(
        meta=_meta("projects", "Projects Report", "تقرير المشاريع", company_id, actor_user_id, db, summary, summary, len(rows)),
        columns=_PROJECT_COLUMNS, rows=rows,
    )


# --- Documents ---

_DOCUMENT_COLUMNS = [
    ReportColumn("file_name", "File name", "اسم الملف"),
    ReportColumn("document_type", "Type", "النوع"),
    ReportColumn("status", "Status", "الحالة"),
    ReportColumn("project", "Project", "المشروع"),
    ReportColumn("file_size", "Size", "الحجم"),
    ReportColumn("created_at", "Uploaded", "تاريخ الرفع"),
]


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def build_documents_report(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, actor_role: str, locale: str, filters: dict
) -> ReportData:
    documents = documents_service.list_documents(
        db, company_id=company_id, limit=_MAX_REPORT_ROWS, cursor=None,
        project_id=filters.get("project_id"), document_type=filters.get("document_type"),
        status=filters.get("status"), filename_search=filters.get("search"),
    )
    project_names = _project_names_for(db, company_id=company_id, project_ids={d.project_id for d in documents})
    rows = [
        {
            "file_name": d.file_name,
            "document_type": _label(d.document_type, locale),
            "status": _label(d.status, locale),
            "project": project_names.get(d.project_id, "") if d.project_id else "",
            "file_size": _human_size(d.file_size_bytes),
            "created_at": _fmt_dt(d.created_at),
        }
        for d in documents
    ]
    parts = []
    if filters.get("status"):
        parts.append(f"Status: {filters['status']}")
    if filters.get("document_type"):
        parts.append(f"Type: {filters['document_type']}")
    summary_en = " | ".join(parts)
    return ReportData(
        meta=_meta("documents", "Documents Report", "تقرير المستندات", company_id, actor_user_id, db, summary_en, summary_en, len(rows)),
        columns=_DOCUMENT_COLUMNS, rows=rows,
    )


# --- Tasks ---

_TASK_COLUMNS = [
    ReportColumn("title", "Title", "العنوان"),
    ReportColumn("status", "Status", "الحالة"),
    ReportColumn("priority", "Priority", "الأولوية"),
    ReportColumn("assignee", "Assignee", "المكلّف"),
    ReportColumn("project", "Project", "المشروع"),
    ReportColumn("due_date", "Due date", "تاريخ الاستحقاق"),
    ReportColumn("created_at", "Created", "تاريخ الإنشاء"),
]


def build_tasks_report(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, actor_role: str, locale: str, filters: dict
) -> ReportData:
    # Members see exactly what My Tasks/Team Tasks show them: their own
    # tasks. Management roles see the company-wide roll-up, matching
    # Team Tasks -- both are the SAME RLS policy the app already
    # enforces (per-row: project tasks are company-wide visible; a
    # personal task is visible to its creator/assignee, or to
    # owner/admin/manager), not a new rule invented for reporting.
    assigned_to = actor_user_id if actor_role not in _MANAGEMENT_ROLES else filters.get("assigned_to")
    tasks = tasks_repository.list_tasks(
        db, company_id=company_id, limit=_MAX_REPORT_ROWS, cursor=None,
        assigned_to=assigned_to, status=filters.get("status"), priority=filters.get("priority"),
        project_id=filters.get("project_id"), due_filter=filters.get("due_filter"), search=filters.get("search"),
    )
    project_names = _project_names_for(db, company_id=company_id, project_ids={t.project_id for t in tasks})
    user_ids = {t.assigned_to for t in tasks if t.assigned_to} | {t.created_by for t in tasks}
    user_names = _user_names_for(db, user_ids=user_ids)
    rows = [
        {
            "title": t.title,
            "status": _label(t.status, locale),
            "priority": _label(t.priority, locale),
            "assignee": user_names.get(t.assigned_to, "") if t.assigned_to else ("Unassigned" if locale != "ar" else "غير مسندة"),
            "project": project_names.get(t.project_id, "") if t.project_id else "",
            "due_date": _fmt_date(t.due_date),
            "created_at": _fmt_dt(t.created_at),
        }
        for t in tasks
    ]
    parts = []
    if filters.get("status"):
        parts.append(f"Status: {filters['status']}")
    if filters.get("priority"):
        parts.append(f"Priority: {filters['priority']}")
    if filters.get("due_filter"):
        parts.append(f"Due: {filters['due_filter']}")
    summary_en = " | ".join(parts)
    return ReportData(
        meta=_meta("tasks", "Tasks Report", "تقرير المهام", company_id, actor_user_id, db, summary_en, summary_en, len(rows)),
        columns=_TASK_COLUMNS, rows=rows,
    )


# --- Daily Brief ---

_BRIEF_COLUMNS = [
    ReportColumn("category", "Category", "الفئة"),
    ReportColumn("priority", "Priority", "الأولوية"),
    ReportColumn("text", "Item", "البند"),
]

_BRIEF_CATEGORY_LABELS_EN = {
    "new_information": "New Information", "pending_action": "Pending Action",
    "follow_up": "Follow-up", "potential_issue": "Potential Issue",
}
_BRIEF_CATEGORY_LABELS_AR = {
    "new_information": "معلومات جديدة", "pending_action": "إجراء معلّق",
    "follow_up": "متابعة", "potential_issue": "مشكلة محتملة",
}


def build_daily_brief_report(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, actor_role: str, locale: str, filters: dict
) -> ReportData:
    brief_date_str = filters.get("date")
    if brief_date_str:
        brief = briefs_repository.get_daily_brief_by_date(
            db, company_id=company_id, brief_date=date.fromisoformat(brief_date_str)
        )
    else:
        brief = briefs_repository.get_latest_daily_brief(db, company_id=company_id)

    rows: list[dict] = []
    resolved_date = ""
    if brief is not None:
        items = briefs_repository.list_brief_items(db, company_id=company_id, brief_id=brief.id)
        category_labels = _BRIEF_CATEGORY_LABELS_AR if locale == "ar" else _BRIEF_CATEGORY_LABELS_EN
        rows = [
            {
                "category": category_labels.get(item.category, item.category),
                "priority": str(item.priority),
                "text": item.text,
            }
            for item in items
        ]
        resolved_date = brief.brief_date.isoformat()

    summary_en = f"Brief date: {resolved_date}" if resolved_date else "No brief available for the requested date."
    summary_ar = f"تاريخ الموجز: {resolved_date}" if resolved_date else "لا يوجد موجز للتاريخ المطلوب."
    return ReportData(
        meta=_meta("daily_brief", "Daily Brief Report", "تقرير الموجز اليومي", company_id, actor_user_id, db, summary_en, summary_ar, len(rows)),
        columns=_BRIEF_COLUMNS, rows=rows,
    )


# --- Audit Log (owner/admin only -- enforced by the router, not here) ---

_AUDIT_COLUMNS = [
    ReportColumn("created_at", "Time", "الوقت"),
    ReportColumn("actor", "Actor", "الفاعل"),
    ReportColumn("action", "Action", "الإجراء"),
    ReportColumn("resource_type", "Resource", "المورد"),
    ReportColumn("ip_address", "IP Address", "عنوان IP"),
]


def build_audit_log_report(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, actor_role: str, locale: str, filters: dict
) -> ReportData:
    date_from = datetime.fromisoformat(filters["date_from"]) if filters.get("date_from") else None
    date_to = datetime.fromisoformat(filters["date_to"]) if filters.get("date_to") else None
    entries = audit_log_repository.list_audit_logs(
        db, company_id=company_id, limit=_MAX_REPORT_ROWS, cursor=None,
        action=filters.get("action"), resource_type=filters.get("resource_type"),
        actor_user_id=None, date_from=date_from, date_to=date_to,
    )
    actor_ids = {e.actor_user_id for e in entries if e.actor_user_id}
    actor_names = _user_names_for(db, user_ids=actor_ids)
    system_label = "System" if locale != "ar" else "النظام"
    rows = [
        {
            "created_at": _fmt_dt(e.created_at),
            "actor": actor_names.get(e.actor_user_id, system_label) if e.actor_user_id else system_label,
            "action": e.action,
            "resource_type": e.resource_type,
            "ip_address": e.ip_address or "",
        }
        for e in entries
    ]
    parts = []
    if filters.get("action"):
        parts.append(f"Action: {filters['action']}")
    if filters.get("resource_type"):
        parts.append(f"Resource: {filters['resource_type']}")
    summary_en = " | ".join(parts)
    return ReportData(
        meta=_meta("audit_log", "Audit Log Report", "تقرير سجل التدقيق", company_id, actor_user_id, db, summary_en, summary_en, len(rows)),
        columns=_AUDIT_COLUMNS, rows=rows,
    )


# --- Support Tickets (always creator-private -- see support/models.py's
# SupportTicket docstring; a report never widens this to company-wide,
# even for owner/admin, matching the deliberate Step 17 design) ---

_TICKET_COLUMNS = [
    ReportColumn("reference_code", "Reference", "المرجع"),
    ReportColumn("subject", "Subject", "الموضوع"),
    ReportColumn("category", "Category", "الفئة"),
    ReportColumn("priority", "Priority", "الأولوية"),
    ReportColumn("status", "Status", "الحالة"),
    ReportColumn("created_at", "Created", "تاريخ الإنشاء"),
]


def build_support_tickets_report(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, actor_role: str, locale: str, filters: dict
) -> ReportData:
    tickets = support_service.list_tickets(
        db, company_id=company_id, actor_user_id=actor_user_id, limit=_MAX_REPORT_ROWS,
        status=filters.get("status"), cursor=None,
    )
    rows = [
        {
            "reference_code": t.reference_code,
            "subject": t.subject,
            "category": t.category,
            "priority": _label(t.priority, locale),
            "status": _label(t.status, locale),
            "created_at": _fmt_dt(t.created_at),
        }
        for t in tickets
    ]
    summary_en = f"Status: {filters['status']}" if filters.get("status") else ""
    return ReportData(
        meta=_meta("support_tickets", "My Support Tickets Report", "تقرير تذاكر الدعم الخاصة بي", company_id, actor_user_id, db, summary_en, summary_en, len(rows)),
        columns=_TICKET_COLUMNS, rows=rows,
    )


# --- Collaboration (self-scoped: the caller's own conversations, no
# message content -- see collaboration.service.list_conversations,
# already actor-scoped by conversation membership) ---

_COLLABORATION_COLUMNS = [
    ReportColumn("name", "Conversation", "المحادثة"),
    ReportColumn("type", "Type", "النوع"),
    ReportColumn("project", "Project", "المشروع"),
    ReportColumn("created_at", "Created", "تاريخ الإنشاء"),
    ReportColumn("updated_at", "Last activity", "آخر نشاط"),
]

_CONVERSATION_TYPE_LABELS_EN = {"direct": "Direct", "group": "Group", "project_channel": "Project channel"}
_CONVERSATION_TYPE_LABELS_AR = {"direct": "مباشرة", "group": "مجموعة", "project_channel": "قناة مشروع"}


def build_collaboration_report(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, actor_role: str, locale: str, filters: dict
) -> ReportData:
    conversations = collaboration_service.list_conversations(
        db, company_id=company_id, actor_user_id=actor_user_id, limit=_MAX_REPORT_ROWS, cursor=None,
    )
    project_names = _project_names_for(db, company_id=company_id, project_ids={c.project_id for c in conversations})
    type_labels = _CONVERSATION_TYPE_LABELS_AR if locale == "ar" else _CONVERSATION_TYPE_LABELS_EN
    unnamed = "Untitled" if locale != "ar" else "بدون عنوان"
    rows = [
        {
            "name": c.name or unnamed,
            "type": type_labels.get(c.type, c.type),
            "project": project_names.get(c.project_id, "") if c.project_id else "",
            "created_at": _fmt_dt(c.created_at),
            "updated_at": _fmt_dt(c.updated_at),
        }
        for c in conversations
    ]
    return ReportData(
        meta=_meta("collaboration", "My Conversations Report", "تقرير محادثاتي", company_id, actor_user_id, db, "", "", len(rows)),
        columns=_COLLABORATION_COLUMNS, rows=rows,
    )


def _meta(
    report_type: str, title_en: str, title_ar: str, company_id: uuid.UUID, actor_user_id: uuid.UUID,
    db: Session, filters_summary_en: str, filters_summary_ar: str, row_count: int,
) -> ReportMeta:
    from datetime import UTC

    from app.modules.reports.service import generate_reference_number
    from app.modules.tenancy import repository as tenancy_repository

    company = tenancy_repository.get_company_by_id(db, company_id)
    return ReportMeta(
        report_type=report_type, title_en=title_en, title_ar=title_ar,
        company_id=company_id, company_name=company.name if company else "",
        generated_at=datetime.now(UTC), generated_by_name=_actor_display_name(db, actor_user_id),
        reference_number=generate_reference_number(report_type),
        filters_summary_en=filters_summary_en, filters_summary_ar=filters_summary_ar,
        row_count=row_count,
    )


BUILDERS = {
    "projects": build_projects_report,
    "documents": build_documents_report,
    "tasks": build_tasks_report,
    "daily_brief": build_daily_brief_report,
    "audit_log": build_audit_log_report,
    "support_tickets": build_support_tickets_report,
    "collaboration": build_collaboration_report,
}

