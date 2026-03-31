from datetime import datetime
from typing import Optional

from app.application.services.document.document_query_service.document_query_service_settings import (
    DocumentQueryServiceSettings,
)
from app.application.services.document.document_query_service.exceptions.document_query_service_exception import (
    DocumentQueryInvalidRequestException,
)


class DocumentQueryServiceValidator:
    def __init__(self, document_query_service_settings: DocumentQueryServiceSettings) -> None:
        self._settings = document_query_service_settings

    def validate_document_id(self, document_id: int) -> None:
        if document_id <= 0:
            raise DocumentQueryInvalidRequestException(
                f"document_id must be a positive integer, got {document_id}"
            )

    def validate_pagination(self, page: Optional[int], size: Optional[int]) -> None:
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

    def validate_filters(
            self,
            name: Optional[str],
            description: Optional[str],
            category: Optional[str],
            created_from: Optional[datetime],
            created_to: Optional[datetime],
    ) -> None:
        for field_name, field_value in (
                ("name", name),
                ("description", description),
                ("category", category),
        ):
            if field_value is None:
                continue
            if len(field_value) > self._settings.max_filter_length:
                raise DocumentQueryInvalidRequestException(
                    f"{field_name} exceeds max length {self._settings.max_filter_length}"
                )

        if created_from and created_to and created_from > created_to:
            raise DocumentQueryInvalidRequestException(
                "created_from cannot be greater than created_to"
            )
