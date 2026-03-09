from app.application.exceptions.app_exception import AppException


class EmbedderException(AppException):
    pass


class UnsupportedEmbedderTypeException(EmbedderException):
    pass


class EmbedderInitializationException(EmbedderException):
    pass


class EmbedDocumentsException(EmbedderException):
    pass


class EmbedQueryException(EmbedderException):
    pass
