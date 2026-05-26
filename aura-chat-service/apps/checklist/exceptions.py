from core.exceptions.base import ForbiddenException, NotFoundException


class ChecklistNotFoundException(NotFoundException):
    error_code = "checklist_not_found"
    detail = "Checklist no encontrada."


class ChecklistAccessDeniedException(ForbiddenException):
    error_code = "checklist_access_denied"
    detail = "No tenés acceso a esta checklist."
