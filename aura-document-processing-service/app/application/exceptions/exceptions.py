class AppError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code or self.__class__.__name__


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed", *, code: str | None = None):
        super().__init__(message, status_code=422, code=code)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", *, code: str | None = None):
        super().__init__(message, status_code=404, code=code)


class UnsupportedFileTypeError(AppError):
    def __init__(self, message: str = "Unsupported file type", *, code: str | None = None):
        super().__init__(message, status_code=415, code=code)


class StorageError(AppError):
    def __init__(self, message: str = "Storage operation failed", *, code: str | None = None):
        super().__init__(message, status_code=502, code=code)

class DatabaseError(AppError):
    def __init__(self, message: str = "Database operation failed", *, code: str | None = None):
        super().__init__(message, status_code=500, code=code)


class ConfigError(AppError):
    def __init__(self, message: str = "Invalid configuration", *, code: str | None = None):
        super().__init__(message, status_code=500, code=code)