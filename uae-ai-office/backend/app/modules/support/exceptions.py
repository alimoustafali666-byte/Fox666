from app.core.exceptions import AppError


class SupportTicketNotFoundError(AppError):
    """Used when a ticket genuinely doesn't exist, belongs to another
    company, or belongs to a different user (creator-private) --
    deliberately identical in all three cases (IDOR protection), same
    rationale as app.modules.conversations.exceptions.ConversationNotFoundError.
    """

    status_code = 404
    code = "support_ticket_not_found"


class SupportTicketRateLimitedError(AppError):
    status_code = 429
    code = "support_ticket_rate_limited"


class SupportAssistantRateLimitedError(AppError):
    status_code = 429
    code = "support_assistant_rate_limited"


class SupportAssistantUnavailableError(AppError):
    """Generic, safe error for any failure reaching the API boundary while
    answering a support question -- never carries a vendor exception's
    raw text or an API key.
    """

    status_code = 503
    code = "support_assistant_unavailable"


class BlankSupportQuestionError(AppError):
    status_code = 400
    code = "blank_support_question"


class InvalidTicketStatusTransitionError(AppError):
    status_code = 400
    code = "invalid_ticket_status_transition"

