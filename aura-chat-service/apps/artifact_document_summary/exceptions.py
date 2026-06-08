from core.exceptions.base import ForbiddenException, NotFoundException, ServiceException, ServiceUnavailableException


class DocumentSummaryNotFoundException(NotFoundException):
    error_code = "document_summary_not_found"
    detail = "Resumen de documento no encontrado."


class DocumentSummaryAccessDeniedException(ForbiddenException):
    error_code = "document_summary_access_denied"
    detail = "No tenés acceso a este resumen de documento."


class LLMServiceException(ServiceUnavailableException):
    status_code = 502
    error_code = "llm_service_error"
    detail = "El servicio de generación no está disponible. Intentá de nuevo más tarde."


class DocumentSummaryExportException(ServiceException):
    status_code = 500
    error_code = "document_summary_export_failed"
    detail = "No se pudo generar la exportación del resumen."
