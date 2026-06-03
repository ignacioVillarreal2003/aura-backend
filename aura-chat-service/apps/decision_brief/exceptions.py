from core.exceptions.base import ForbiddenException, NotFoundException, ServiceException, ServiceUnavailableException


class DecisionBriefNotFoundException(NotFoundException):
    error_code = "decision_brief_not_found"
    detail = "Brief de decisión no encontrado."


class DecisionBriefAccessDeniedException(ForbiddenException):
    error_code = "decision_brief_access_denied"
    detail = "No tenés acceso a este brief de decisión."


class LLMServiceException(ServiceUnavailableException):
    status_code = 502
    error_code = "llm_service_error"
    detail = "El servicio de generación no está disponible. Intentá de nuevo más tarde."


class DecisionBriefExportException(ServiceException):
    status_code = 500
    error_code = "decision_brief_export_failed"
    detail = "No se pudo generar la exportación del brief de decisión."
