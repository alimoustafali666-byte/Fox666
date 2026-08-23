from app.core.exceptions import AppError


class ProjectNotFoundError(AppError):
    """Used both when a project genuinely doesn't exist and when it
    belongs to another company -- deliberately identical (IDOR
    protection): a caller must never be able to tell "wrong tenant" from
    "never existed" apart from the response.
    """

    status_code = 404
    code = "project_not_found"


class ProjectCodeAlreadyExistsError(AppError):
    """Generic on purpose -- confirms the code is taken within the
    caller's own company without revealing anything about the project
    that's using it (name, id, status, ...).
    """

    status_code = 409
    code = "project_code_already_exists"

