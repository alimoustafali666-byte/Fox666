from app.core.exceptions import AppError


class ConversationNotFoundError(AppError):
    """Used when a conversation genuinely doesn't exist, belongs to
    another company, or belongs to a different user (creator-private) --
    deliberately identical in all three cases (IDOR protection): a caller
    must never be able to tell "wrong tenant" / "someone else's" /
    "never existed" apart from the response. RLS on `conversations`
    already makes the two tenant/creator cases physically unreadable;
    this exception is what the repository layer raises when its own
    (defense-in-depth) query also finds nothing.
    """

    status_code = 404
    code = "conversation_not_found"


class BlankQuestionError(AppError):
    status_code = 400
    code = "blank_question"


class QuestionTooLongError(AppError):
    status_code = 400
    code = "question_too_long"


class InvalidDocumentTypeFilterError(AppError):
    status_code = 400
    code = "invalid_document_type"


class AskUnavailableError(AppError):
    """Generic, safe error for any failure reaching the API boundary while
    answering a question -- retrieval-provider failure or LLM-provider
    failure alike. Never carries a vendor exception's raw text, an API
    key, or a raw model response.
    """

    status_code = 503
    code = "ask_unavailable"

