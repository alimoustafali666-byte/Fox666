from app.core.exceptions import AppError


class UnknownReportTypeError(AppError):
    status_code = 404
    code = "unknown_report_type"


class UnsupportedReportFormatError(AppError):
    status_code = 400
    code = "unsupported_report_format"

