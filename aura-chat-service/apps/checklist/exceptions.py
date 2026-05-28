from core.exceptions.base import ForbiddenException, NotFoundException, ServiceUnavailableException


class ChecklistNotFoundException(NotFoundException):
    error_code = "checklist_not_found"
    detail = "Checklist no encontrada."


class ChecklistAccessDeniedException(ForbiddenException):
    error_code = "checklist_access_denied"
    detail = "No tenés acceso a esta checklist."


class LLMServiceException(ServiceUnavailableException):
    status_code = 502
    error_code = "llm_service_error"
    detail = "El servicio de generación no está disponible. Intentá de nuevo más tarde."
