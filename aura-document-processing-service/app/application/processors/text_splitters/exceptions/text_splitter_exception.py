from app.application.exceptions.app_exception import AppException


class TextSplitterException(AppException):
    pass


class UnsupportedTextSplitterTypeException(TextSplitterException):
    pass


class TextSplitterInitializationException(TextSplitterException):
    pass


class TextSplitterExecutionException(TextSplitterException):
    pass
