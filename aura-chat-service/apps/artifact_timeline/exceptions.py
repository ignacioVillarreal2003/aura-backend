from core.exceptions.base import ForbiddenException, NotFoundException, ServiceException, ServiceUnavailableException


class TimelineNotFoundException(NotFoundException):
    error_code = "timeline_not_found"
    detail = "Línea de tiempo no encontrada."


class TimelineAccessDeniedException(ForbiddenException):
    error_code = "timeline_access_denied"
    detail = "No tenés acceso a esta línea de tiempo."


class LLMServiceException(ServiceUnavailableException):
    status_code = 502
    error_code = "llm_service_error"
    detail = "El servicio de generación no está disponible. Intentá de nuevo más tarde."


class TimelineExportException(ServiceException):
    status_code = 500
    error_code = "timeline_export_failed"
    detail = "No se pudo generar la exportación de la línea de tiempo."
