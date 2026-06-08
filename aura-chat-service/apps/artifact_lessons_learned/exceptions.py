from core.exceptions.base import ForbiddenException, NotFoundException, ServiceException, ServiceUnavailableException


class LessonsLearnedNotFoundException(NotFoundException):
    error_code = "lessons_learned_not_found"
    detail = "Lecciones aprendidas no encontradas."


class LessonsLearnedAccessDeniedException(ForbiddenException):
    error_code = "lessons_learned_access_denied"
    detail = "No tenés acceso a estas lecciones aprendidas."


class LLMServiceException(ServiceUnavailableException):
    status_code = 502
    error_code = "llm_service_error"
    detail = "El servicio de generación no está disponible. Intentá de nuevo más tarde."


class LessonsLearnedExportException(ServiceException):
    status_code = 500
    error_code = "lessons_learned_export_failed"
    detail = "No se pudo generar la exportación de las lecciones aprendidas."
