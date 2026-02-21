from app.application.exceptions.app_exception import AppException


class TextCleanerException(AppException):
    pass


class UnsupportedTextCleanerTypeException(TextCleanerException):
    pass
