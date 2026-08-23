"""Safe diagnostic-metadata builder -- an ALLOWLIST, not a denylist (Step
17 requirement). This is the only place in the support module allowed to
construct the small dict of "safe product state" handed to the Support
Assistant or attached to a new ticket.

Never includes: passwords, API keys, JWTs, refresh tokens, cookies,
authorization headers, raw document content, Claude prompts, full AI
conversations, embedding vectors, storage keys, or any other company-
confidential data -- none of those concepts are even inputs to this
module. Every dict this module builds is additionally passed through
app.modules.audit_log.sanitizer.sanitize_metadata before being returned,
so a mistake here still can't persist a credential- or token-shaped
value -- the same defense-in-depth discipline used for every audit event
in the codebase.
"""

import uuid

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.modules.audit_log.sanitizer import sanitize_metadata
from app.modules.auth.service import TenantContext
from app.modules.documents import service as documents_service
from app.modules.documents.exceptions import DocumentNotFoundError
from app.modules.projects import service as projects_service
from app.modules.projects.exceptions import ProjectNotFoundError


class DiagnosticsInput(BaseModel):
    """What a client is allowed to volunteer. Every field is optional,
    bounded, and inherently safe even if taken at face value -- none of
    them is trusted as an authorization check (document_id/project_id
    are re-fetched company-scoped below, never assumed accessible just
    because the client sent an id).
    """

    page: str | None = Field(default=None, max_length=200)
    document_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    user_agent_summary: str | None = Field(default=None, max_length=200)
    app_version: str | None = Field(default=None, max_length=50)


def build_diagnostics(
    db: Session, *, context: TenantContext, data: DiagnosticsInput
) -> dict:
    diagnostics: dict = {
        "role": context.role,
        "company_id": str(context.company_id),
    }
    if data.page:
        diagnostics["page"] = data.page
    if data.user_agent_summary:
        diagnostics["user_agent_summary"] = data.user_agent_summary
    if data.app_version:
        diagnostics["app_version"] = data.app_version

    if data.document_id is not None:
        try:
            document = documents_service.get_document(
                db, company_id=context.company_id, document_id=data.document_id
            )
        except DocumentNotFoundError:
            pass
        else:
            diagnostics["document_id"] = str(document.id)
            diagnostics["document_type"] = document.document_type
            diagnostics["document_status"] = document.status
            diagnostics["document_indexing_status"] = document.indexing_status
            if document.processing_error_code:
                diagnostics["document_processing_error_code"] = document.processing_error_code
            if document.indexing_error_code:
                diagnostics["document_indexing_error_code"] = document.indexing_error_code

    if data.project_id is not None:
        try:
            project = projects_service.get_project(
                db, company_id=context.company_id, project_id=data.project_id
            )
        except ProjectNotFoundError:
            pass
        else:
            diagnostics["project_id"] = str(project.id)
            diagnostics["project_status"] = project.status

    return sanitize_metadata(diagnostics) or {}

