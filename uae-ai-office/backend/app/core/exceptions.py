class AppError(Exception):
    """Base for typed domain exceptions. Routers never format HTTP
    responses themselves -- they raise one of these, and a single
    exception handler (registered in app.main) turns it into the
    consistent {"error": {"code", "message"}} envelope. This is also the
    one place responsible for making sure nothing exposes a stack trace,
    a raw exception message, or internal details to the client.
    """

    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class BadRequestError(AppError):
    """Generic 400 for malformed client input that doesn't warrant its
    own module-specific exception type (e.g. an invalid pagination
    cursor).
    """

    status_code = 400
    code = "bad_request"

