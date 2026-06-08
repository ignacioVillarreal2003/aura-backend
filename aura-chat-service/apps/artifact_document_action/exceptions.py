from core.exceptions.base import ForbiddenException, NotFoundException, ServiceException, ServiceUnavailableException


class DocumentActionNotFoundException(NotFoundException):
    error_code = "document_action_not_found"
    detail = "Acción sobre documento no encontrada."


class DocumentActionAccessDeniedException(ForbiddenException):
    error_code = "document_action_access_denied"
    detail = "No tenés acceso a esta acción sobre documento."


class LLMServiceException(ServiceUnavailableException):
    status_code = 502
    error_code = "llm_service_error"
    detail = "El servicio de generación no está disponible. Intentá de nuevo más tarde."


class DocumentActionExportException(ServiceException):
    status_code = 500
    error_code = "document_action_export_failed"
    detail = "No se pudo generar la exportación de la acción."
