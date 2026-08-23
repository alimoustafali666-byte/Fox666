import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.request_ip import get_client_ip
from app.db.session import get_db
from app.modules.auth.dependencies import get_tenant_context
from app.modules.auth.service import TenantContext
from app.modules.reports import service
from app.modules.reports.rendering import ReportData
from app.modules.reports.schemas import (
    DashboardSummaryResponse,
    ReportColumnPublic,
    ReportPreviewMeta,
    ReportPreviewResponse,
    ReportTypeInfo,
)

router = APIRouter(prefix="/reports", tags=["reports"])

_ALLOWED_LOCALES = ("en", "ar")


def _resolve_locale(locale: str | None) -> str:
    return locale if locale in _ALLOWED_LOCALES else "en"


def _collect_filters(
    *,
    status: str | None,
    priority: str | None,
    project_id: uuid.UUID | None,
    document_type: str | None,
    due_filter: str | None,
    search: str | None,
    date: str | None,
    date_from: str | None,
    date_to: str | None,
    action: str | None,
    resource_type: str | None,
    assigned_to: uuid.UUID | None,
) -> dict:
    values = {
        "status": status, "priority": priority, "project_id": project_id, "document_type": document_type,
        "due_filter": due_filter, "search": search, "date": date, "date_from": date_from, "date_to": date_to,
        "action": action, "resource_type": resource_type, "assigned_to": assigned_to,
    }
    return {k: v for k, v in values.items() if v is not None}


def _preview_response(data: ReportData, *, locale: str) -> ReportPreviewResponse:
    title = data.meta.title_ar if locale == "ar" else data.meta.title_en
    filters_summary = data.meta.filters_summary_ar if locale == "ar" else data.meta.filters_summary_en
    columns = [
        ReportColumnPublic(key=c.key, label=(c.label_ar if locale == "ar" else c.label_en))
        for c in data.columns
    ]
    return ReportPreviewResponse(
        meta=ReportPreviewMeta(
            report_type=data.meta.report_type, title=title, company_name=data.meta.company_name,
            generated_at=data.meta.generated_at, generated_by=data.meta.generated_by_name,
            reference_number=data.meta.reference_number, filters_summary=filters_summary,
            row_count=data.meta.row_count,
        ),
        columns=columns, rows=data.rows,
    )


@router.get("/types", response_model=list[ReportTypeInfo])
def list_report_types(
    context: TenantContext = Depends(get_tenant_context),
) -> list[ReportTypeInfo]:
    return [
        ReportTypeInfo(type=report_type, title_en=title_en, title_ar=title_ar)
        for report_type, (title_en, title_ar, allowed_roles) in service.REPORT_TYPES.items()
        if allowed_roles is None or context.role in allowed_roles
    ]


@router.get("/dashboard-summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> DashboardSummaryResponse:
    summary = service.get_dashboard_summary(
        db, company_id=context.company_id, actor_user_id=context.user.id, actor_role=context.role
    )
    return DashboardSummaryResponse(**summary)


@router.get("/{report_type}/preview", response_model=ReportPreviewResponse)
def preview_report(
    report_type: str,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    locale: str | None = Query(default=None),
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    project_id: uuid.UUID | None = Query(default=None),
    document_type: str | None = Query(default=None),
    due_filter: str | None = Query(default=None),
    search: str | None = Query(default=None),
    date: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    assigned_to: uuid.UUID | None = Query(default=None),
) -> ReportPreviewResponse:
    resolved_locale = _resolve_locale(locale)
    filters = _collect_filters(
        status=status, priority=priority, project_id=project_id, document_type=document_type,
        due_filter=due_filter, search=search, date=date, date_from=date_from, date_to=date_to,
        action=action, resource_type=resource_type, assigned_to=assigned_to,
    )
    data = service.build_report_data(
        db, company_id=context.company_id, actor_user_id=context.user.id, actor_role=context.role,
        report_type=report_type, locale=resolved_locale, filters=filters,
    )
    return _preview_response(data, locale=resolved_locale)


@router.get("/{report_type}")
def download_report(
    report_type: str,
    request: Request,
    format: str = Query(...),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    locale: str | None = Query(default=None),
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    project_id: uuid.UUID | None = Query(default=None),
    document_type: str | None = Query(default=None),
    due_filter: str | None = Query(default=None),
    search: str | None = Query(default=None),
    date: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    assigned_to: uuid.UUID | None = Query(default=None),
) -> Response:
    resolved_locale = _resolve_locale(locale)
    filters = _collect_filters(
        status=status, priority=priority, project_id=project_id, document_type=document_type,
        due_filter=due_filter, search=search, date=date, date_from=date_from, date_to=date_to,
        action=action, resource_type=resource_type, assigned_to=assigned_to,
    )
    file_bytes, content_type, filename = service.render_report_file(
        db, company_id=context.company_id, actor_user_id=context.user.id, actor_role=context.role,
        report_type=report_type, export_format=format, locale=resolved_locale, filters=filters,
        ip_address=get_client_ip(request),
    )
    # ASCII-safe filename by construction (see service._safe_filename_component)
    # -- no need for RFC 5987 filename* encoding here.
    return Response(
        content=file_bytes, media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

