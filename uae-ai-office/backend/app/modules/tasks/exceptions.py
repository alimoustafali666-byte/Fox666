from app.core.exceptions import AppError


class TaskNotFoundError(AppError):
    """Used when a task genuinely doesn't exist, belongs to another
    company, or the caller isn't authorized to see it (RLS already hides
    those rows) -- deliberately identical in all cases (IDOR protection),
    same convention as ProjectNotFoundError/DocumentNotFoundError.
    """

    status_code = 404
    code = "task_not_found"


class NotTaskAuthorizedError(AppError):
    """The task is visible (findable) but the specific action isn't
    permitted for this role/relationship to the task -- e.g. a plain
    member trying to change a field beyond their own assigned task's
    status.
    """

    status_code = 403
    code = "not_task_authorized"


class InvalidTaskStatusTransitionError(AppError):
    status_code = 400
    code = "invalid_task_status_transition"


class InvalidAssigneeError(AppError):
    """The requested assignee isn't a member of the acting company, or
    the acting role isn't permitted to assign to someone other than
    themselves.
    """

    status_code = 400
    code = "invalid_assignee"


class InvalidSourceReferenceError(AppError):
    """The declared source_id doesn't exist, or the acting user isn't
    currently authorized to access it -- covers both "not found" and
    "not yours" identically, same IDOR discipline as every other
    not-found error in this app.
    """

    status_code = 400
    code = "invalid_source_reference"


class TaskCommentNotFoundError(AppError):
    status_code = 404
    code = "task_comment_not_found"

