from core.exceptions.base import ForbiddenException, NotFoundException, ServiceException, ServiceUnavailableException


class ReportNotFoundException(NotFoundException):
    error_code = "report_not_found"
    detail = "Informe no encontrado."


class ReportAccessDeniedException(ForbiddenException):
    error_code = "report_access_denied"
    detail = "No tenés acceso a este informe."


class LLMServiceException(ServiceUnavailableException):
    status_code = 502
    error_code = "llm_service_error"
    detail = "El servicio de generación no está disponible. Intentá de nuevo más tarde."


class ReportExportException(ServiceException):
    status_code = 500
    error_code = "report_export_failed"
    detail = "No se pudo generar la exportación del informe."
