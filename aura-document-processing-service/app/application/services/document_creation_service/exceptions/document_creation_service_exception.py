from app.application.exceptions.app_exception import AppError


class UnsupportedFileTypeError(AppError):
    def __init__(self, message: str = "Tipo de archivo no soportado", *, code: str | None = None):
        super().__init__(message, status_code=415, code=code)
