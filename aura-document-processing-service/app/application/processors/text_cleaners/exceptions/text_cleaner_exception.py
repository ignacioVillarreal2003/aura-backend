from app.application.exceptions.app_exception import AppException


class TextCleanerError(AppException):
    pass


class UnsupportedTextCleanerMethodError(TextCleanerError):
    pass
