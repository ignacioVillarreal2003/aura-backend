from core.exceptions.base import ForbiddenException, NotFoundException, ServiceException, ServiceUnavailableException


class QuizNotFoundException(NotFoundException):
    error_code = "quiz_not_found"
    detail = "Cuestionario no encontrado."


class QuizAccessDeniedException(ForbiddenException):
    error_code = "quiz_access_denied"
    detail = "No tenés acceso a este cuestionario."


class QuizQuestionNotFoundException(NotFoundException):
    error_code = "quiz_question_not_found"
    detail = "Pregunta del cuestionario no encontrada."


class QuizOptionNotFoundException(NotFoundException):
    error_code = "quiz_option_not_found"
    detail = "Opción no encontrada para esta pregunta."


class LLMServiceException(ServiceUnavailableException):
    status_code = 502
    error_code = "llm_service_error"
    detail = "El servicio de generación no está disponible. Intentá de nuevo más tarde."


class QuizExportException(ServiceException):
    status_code = 500
    error_code = "quiz_export_failed"
    detail = "No se pudo generar la exportación del cuestionario."
