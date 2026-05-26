from core.exceptions.base import ForbiddenException, NotFoundException


class ReportNotFoundException(NotFoundException):
    error_code = "report_not_found"
    detail = "Informe no encontrado."


class ReportAccessDeniedException(ForbiddenException):
    error_code = "report_access_denied"
    detail = "No tenés acceso a este informe."
