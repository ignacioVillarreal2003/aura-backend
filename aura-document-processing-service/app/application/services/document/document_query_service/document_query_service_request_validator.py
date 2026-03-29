import logging

from app.application.services.document.document_query_service.document_query_service_settings import (
    DocumentQueryServiceSettings
)
from app.application.services.document.document_query_service.exceptions.document_query_service_exception import (
    DocumentQueryInvalidRequestException
)

logger = logging.getLogger(__name__)


class DocumentQueryServiceRequestValidator:
    def __init__(self, document_query_service_settings: DocumentQueryServiceSettings) -> None:
        self._settings = document_query_service_settings

    def validate_pagination(self, page: int | None, size: int | None) -> None:
        if page is not None and page < 1:
            raise DocumentQueryInvalidRequestException(
                f"page must be a positive integer, got {page}"
            )
        if size is not None:
            if size < 1:
                raise DocumentQueryInvalidRequestException(
                    f"size must be a positive integer, got {size}"
                )
            if size > self._settings.max_page_size:
                raise DocumentQueryInvalidRequestException(
                    f"size ({size}) exceeds the maximum allowed page size "
                    f"({self._settings.max_page_size})"
                )
