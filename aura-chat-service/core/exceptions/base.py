class ServiceException(Exception):
    status_code: int = 500
    error_code: str = "internal_error"
    detail: str = "An unexpected error occurred"

    def __init__(self, detail: str | None = None, error_code: str | None = None):
        if detail is not None:
            self.detail = detail
        if error_code is not None:
            self.error_code = error_code
        super().__init__(self.detail)


class NotFoundException(ServiceException):
    status_code = 404
    error_code = "not_found"
    detail = "Resource not found"


class ValidationException(ServiceException):
    status_code = 400
    error_code = "validation_error"
    detail = "Invalid input"


class ForbiddenException(ServiceException):
    status_code = 403
    error_code = "forbidden"
    detail = "You do not have permission to perform this action"


class ConflictException(ServiceException):
    status_code = 409
    error_code = "conflict"
    detail = "Resource conflict"


class ServiceUnavailableException(ServiceException):
    status_code = 503
    error_code = "service_unavailable"
    detail = "A dependency service is temporarily unavailable"


class InsufficientPermissionsException(ServiceException):
    """Authenticated caller lacks application-level permissions (HTTP 403, not 401)."""

    status_code = 403
    error_code = "insufficient_permissions"
    detail = "You do not have permission to perform this action"
