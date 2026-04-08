class AppException(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code or self.__class__.__name__


class RequestValidationException(AppException):
    def __init__(self, message: str, status_code: int = 400, *, code: str | None = None):
        super().__init__(message=message, status_code=status_code, code=code)
