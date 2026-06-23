from core.exceptions.base import ForbiddenException, NotFoundException, ServiceException, ServiceUnavailableException


class ChecklistNotFoundException(NotFoundException):
    error_code = "checklist_not_found"
    detail = "ArtifactChecklist no encontrada."


class ChecklistAccessDeniedException(ForbiddenException):
    error_code = "checklist_access_denied"
    detail = "No tenés acceso a esta checklist."


class ChecklistItemNotFoundException(NotFoundException):
    error_code = "checklist_item_not_found"
    detail = "Ítem de checklist no encontrado."


class LLMServiceException(ServiceUnavailableException):
    status_code = 502
    error_code = "llm_service_error"
    detail = "El servicio de generación no está disponible. Intentá de nuevo más tarde."


class ChecklistExportException(ServiceException):
    status_code = 500
    error_code = "checklist_export_failed"
    detail = "No se pudo generar la exportación de la checklist."
