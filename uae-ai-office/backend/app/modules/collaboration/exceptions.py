from app.core.exceptions import AppError


class ConversationNotFoundError(AppError):
    """Used when a conversation genuinely doesn't exist, belongs to
    another company, or the acting user is not (or is no longer) an
    active member -- deliberately identical in all three cases (IDOR
    protection), same rationale as
    app.modules.conversations.exceptions.ConversationNotFoundError.
    """

    status_code = 404
    code = "conversation_not_found"


class MessageNotFoundError(AppError):
    status_code = 404
    code = "message_not_found"


class NotConversationMemberError(AppError):
    status_code = 403
    code = "not_conversation_member"


class NotConversationAdminError(AppError):
    """Raised when an action requires conversation-level owner/admin (e.g.
    adding/removing a group member) and the actor holds neither role.
    """

    status_code = 403
    code = "not_conversation_admin"


class InvalidConversationTypeError(AppError):
    status_code = 400
    code = "invalid_conversation_type"


class CannotRemoveLastAdminError(AppError):
    """Raised when a removal/role-change would leave a group with zero
    owner/admin members. See service.py for the auto-promotion logic that
    normally avoids this on a self-initiated leave; this guards the
    explicit-removal path.
    """

    status_code = 400
    code = "cannot_remove_last_admin"


class InvalidReactionEmojiError(AppError):
    status_code = 400
    code = "invalid_reaction_emoji"


class MessageTooLongError(AppError):
    status_code = 400
    code = "message_too_long"


class BlankMessageError(AppError):
    status_code = 400
    code = "blank_message"


class CannotEditOthersMessageError(AppError):
    status_code = 403
    code = "cannot_edit_others_message"


class CannotDeleteOthersMessageError(AppError):
    status_code = 403
    code = "cannot_delete_others_message"


class AttachmentTooLargeError(AppError):
    status_code = 400
    code = "attachment_too_large"


class UnsupportedAttachmentTypeError(AppError):
    status_code = 400
    code = "unsupported_attachment_type"


class VoiceNoteTooLongError(AppError):
    status_code = 400
    code = "voice_note_too_long"


class DocumentShareNotAuthorizedError(AppError):
    """Raised when a user tries to share a document they cannot
    themselves access -- sharing a message NEVER grants document access
    by itself; the sharer must independently be authorized. See
    service.py's share_document_in_message.
    """

    status_code = 403
    code = "document_share_not_authorized"


class SearchQueryTooLongError(AppError):
    status_code = 400
    code = "search_query_too_long"


class GroupSizeLimitExceededError(AppError):
    status_code = 400
    code = "group_size_limit_exceeded"


class CollaborationRateLimitedError(AppError):
    status_code = 429
    code = "collaboration_rate_limited"


class CallSessionNotFoundError(AppError):
    status_code = 404
    code = "call_session_not_found"


class CallAlreadyActiveError(AppError):
    """Raised when starting a new call in a conversation that already has
    a ringing/active session.
    """

    status_code = 409
    code = "call_already_active"


class AttachmentNotFoundError(AppError):
    status_code = 404
    code = "attachment_not_found"


class NotificationNotFoundError(AppError):
    status_code = 404
    code = "notification_not_found"


class CollaborationAssistantUnavailableError(AppError):
    """Generic, safe error for any failure reaching the AI boundary while
    summarizing/answering about a conversation -- never carries a vendor
    exception's raw text.
    """

    status_code = 503
    code = "collaboration_assistant_unavailable"

