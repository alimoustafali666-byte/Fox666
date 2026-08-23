from app.core.exceptions import AppError


class BriefNotFoundError(AppError):
    """Used when no brief exists for the requested date (or at all) --
    company-scoped only (briefs are a shared artifact, not creator-
    private), so this is never an IDOR-style cross-tenant concern the way
    ConversationNotFoundError is; RLS/company_id filtering alone already
    makes another company's brief physically unreadable in this session.
    """

    status_code = 404
    code = "brief_not_found"


class InvalidBriefDateError(AppError):
    status_code = 400
    code = "invalid_brief_date"


class BriefGenerationUnavailableError(AppError):
    """Generic, safe error for any LLM-provider failure reaching the API
    boundary while generating a brief. Never carries a vendor exception's
    raw text, an API key, or a raw model response.
    """

    status_code = 503
    code = "brief_generation_unavailable"

