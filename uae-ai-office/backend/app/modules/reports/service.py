"""Orchestration: resolves a report_type + format + filters into either
a JSON preview or exported file bytes. This is the ONLY place that
decides which report types exist, which roles may generate which type,
and how a download filename/reference number is built -- the router
depends only on this module, never on app.modules.reports.builders or
.rendering directly.
"""

import secrets
import uuid
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.modules.audit_log import repository as audit_log_repository
from app.modules.audit_log.service import record_audit_event
from app.modules.auth import repository as auth_repository
from app.modules.auth.exceptions import ForbiddenError
from app.modules.briefs import repository as briefs_repository
from app.modules.collaboration import service as collaboration_service
from app.modules.documents import service as documents_service
from app.modules.projects import service as projects_service
from app.modules.reports import builders
from app.modules.reports.exceptions import UnknownReportTypeError, UnsupportedReportFormatError
from app.modules.reports.rendering import CONTENT_TYPES, RENDERERS, ReportData
from app.modules.support import service as support_service
from app.modules.tasks import repository as tasks_repository
from app.modules.tasks import service as tasks_service
from app.modules.tenancy import service as tenancy_service
from app.modules.tenancy.exceptions import LogoNotFoundError

_MANAGEMENT_ROLES = ("owner", "admin", "manager")
_DASHBOARD_SCAN_LIMIT = 500

# (title_en, title_ar, allowed_roles or None for "any company member")
REPORT_TYPES: dict[str, tuple[str, str, tuple[str, ...] | None]] = {
    "projects": ("Projects", "المشاريع", None),
    "documents": ("Documents", "المستندات", None),
    "tasks": ("Tasks", "المهام", None),
    "daily_brief": ("Daily Brief", "الموجز اليومي", None),
    "audit_log": ("Audit Log", "سجل التدقيق", ("owner", "admin")),
    "support_tickets": ("My Support Tickets", "تذاكر الدعم الخاصة بي", None),
    "collaboration": ("My Conversations", "محادثاتي", None),
}

_REFERENCE_CODES = {
    "projects": "PRJ", "documents": "DOC", "tasks": "TSK", "daily_brief": "BRF",
    "audit_log": "AUD", "support_tickets": "TKT", "collaboration": "COL",
}

_EXPORT_FORMATS = ("csv", "xlsx", "docx", "pdf")


def generate_reference_number(report_type: str) -> str:
    code = _REFERENCE_CODES.get(report_type, "RPT")
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return f"RPT-{code}-{stamp}-{secrets.token_hex(3).upper()}"


def _safe_filename_component(value: str, *, max_len: int = 40) -> str:
    """Restrictive allowlist (ASCII letters/digits/space/hyphen/
    underscore only) for anything that ends up inside a
    Content-Disposition header value -- company name is user-editable
    (PATCH /companies/current), so it's untrusted input by the time it
    reaches here, not just display text.
    """
    cleaned = "".join(ch for ch in value if ch.isalnum() or ch in " -_").strip()
    cleaned = " ".join(cleaned.split())  # collapse whitespace runs
    return (cleaned or "Report")[:max_len]


def _check_permission(report_type: str, actor_role: str) -> None:
    if report_type not in REPORT_TYPES:
        raise UnknownReportTypeError(f"Unknown report type '{report_type}'.")
    _, _, allowed_roles = REPORT_TYPES[report_type]
    if allowed_roles is not None and actor_role not in allowed_roles:
        raise ForbiddenError("You do not have permission to generate this report.")


def build_report_data(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: str,
    report_type: str,
    locale: str,
    filters: dict,
) -> ReportData:
    _check_permission(report_type, actor_role)
    builder = builders.BUILDERS[report_type]
    return builder(
        db, company_id=company_id, actor_user_id=actor_user_id, actor_role=actor_role,
        locale=locale, filters=filters,
    )


def render_report_file(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: str,
    report_type: str,
    export_format: str,
    locale: str,
    filters: dict,
    ip_address: str | None,
) -> tuple[bytes, str, str]:
    """Returns (file_bytes, content_type, filename)."""
    if export_format not in _EXPORT_FORMATS:
        raise UnsupportedReportFormatError(f"format must be one of {list(_EXPORT_FORMATS)}.")

    data = build_report_data(
        db, company_id=company_id, actor_user_id=actor_user_id, actor_role=actor_role,
        report_type=report_type, locale=locale, filters=filters,
    )

    if export_format == "pdf":
        try:
            logo_bytes, logo_content_type = tenancy_service.get_company_logo_bytes(db, company_id=company_id)
            data.meta.logo_bytes = logo_bytes
            data.meta.logo_content_type = logo_content_type
        except LogoNotFoundError:
            pass

    file_bytes = RENDERERS[export_format](data, locale=locale)
    content_type = CONTENT_TYPES[export_format]

    company_component = _safe_filename_component(data.meta.company_name)
    date_component = datetime.now(UTC).strftime("%Y%m%d")
    filename = f"{company_component}-{report_type}-{date_component}.{export_format}"

    record_audit_event(
        db, company_id=company_id, actor_user_id=actor_user_id, action="reports.generated",
        resource_type="report",
        metadata={"report_type": report_type, "format": export_format, "row_count": data.meta.row_count},
        ip_address=ip_address,
    )
    db.commit()

    return file_bytes, content_type, filename


def get_dashboard_summary(db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, actor_role: str) -> dict:
    """Executive Dashboard data. Every count/list here comes from a
    normal, already-RLS/RBAC-scoped call to that domain's own service --
    nothing is a new query path, and nothing widens what the acting
    role/relationship would see anywhere else in the app. Management
    roles (owner/admin/manager) additionally see company-wide project/
    document counts and a task roll-up (Projects and Documents are
    already company-wide readable by every role -- see
    projects/documents RLS -- so this isn't new exposure, just
    aggregation) and, for owner/admin only, a recent-activity feed from
    the audit log (matching that endpoint's own existing role gate).
    """
    is_management = actor_role in _MANAGEMENT_ROLES

    projects = projects_service.list_projects(
        db, company_id=company_id, limit=_DASHBOARD_SCAN_LIMIT, cursor=None,
        status=None, project_code=None, name_search=None,
    )
    project_status_counts = dict(Counter(p.status for p in projects))

    documents = documents_service.list_documents(
        db, company_id=company_id, limit=_DASHBOARD_SCAN_LIMIT, cursor=None,
        project_id=None, document_type=None, status=None, filename_search=None,
    )
    document_status_counts = dict(Counter(d.status for d in documents))

    my_tasks = tasks_service.get_dashboard_summary(db, company_id=company_id, actor_user_id=actor_user_id)

    company_tasks: dict[str, int] | None = None
    if is_management:
        company_tasks = {
            "open": tasks_repository.count_tasks(db, company_id=company_id, open_only=True),
            "overdue": tasks_repository.count_tasks(db, company_id=company_id, due_filter="overdue"),
            "blocked": tasks_repository.count_tasks(db, company_id=company_id, status="blocked"),
        }

    latest_brief = briefs_repository.get_latest_daily_brief(db, company_id=company_id)
    brief_summary = None
    if latest_brief is not None:
        items = briefs_repository.list_brief_items(db, company_id=company_id, brief_id=latest_brief.id)
        brief_summary = {
            "brief_date": latest_brief.brief_date.isoformat(),
            "item_count": len(items),
            "summary": latest_brief.summary,
        }

    my_tickets = support_service.list_tickets(
        db, company_id=company_id, actor_user_id=actor_user_id, limit=_DASHBOARD_SCAN_LIMIT,
        status=None, cursor=None,
    )
    ticket_status_counts = dict(Counter(t.status for t in my_tickets))

    unread_notifications = collaboration_service.count_unread_notifications(
        db, company_id=company_id, actor_user_id=actor_user_id
    )

    recent_activity = None
    if actor_role in ("owner", "admin"):
        entries = audit_log_repository.list_audit_logs(db, company_id=company_id, limit=5, cursor=None)
        actor_ids = {e.actor_user_id for e in entries if e.actor_user_id}
        names = {}
        for uid in actor_ids:
            user = auth_repository.get_user_by_id(db, uid)
            if user is not None:
                names[uid] = user.full_name or user.email
        recent_activity = [
            {
                "created_at": e.created_at.isoformat(),
                "actor": names.get(e.actor_user_id, "System"),
                "action": e.action,
                "resource_type": e.resource_type,
            }
            for e in entries
        ]

    return {
        "project_status_counts": project_status_counts,
        "document_status_counts": document_status_counts,
        "my_tasks": my_tasks,
        "company_tasks": company_tasks,
        "latest_brief": brief_summary,
        "my_ticket_status_counts": ticket_status_counts,
        "unread_notifications": unread_notifications,
        "recent_activity": recent_activity,
    }

