from datetime import datetime
from typing import Optional

from app.application.services.document.document_query_service.document_query_service_settings import (
    DocumentQueryServiceSettings
)
from app.application.services.document.document_query_service.exceptions.document_query_service_exception import (
    DocumentQueryInvalidRequestException
)


class DocumentQueryServiceValidator:
    def __init__(
            self,
            document_query_service_settings: DocumentQueryServiceSettings
    ) -> None:
        self._settings = document_query_service_settings

    @staticmethod
    def validate_document_id(document_id: int) -> None:
        if document_id <= 0:
            raise DocumentQueryInvalidRequestException("The document identifier must be a positive number.")

    def validate_pagination(
            self,
            page: Optional[int],
            size: Optional[int]
    ) -> None:
        if page is not None and page < 1:
            raise DocumentQueryInvalidRequestException("The page number must be a positive integer.")
        if size is not None:
            if size < 1:
                raise DocumentQueryInvalidRequestException("The page size must be a positive integer.")
            if size > self._settings.max_page_size:
                raise DocumentQueryInvalidRequestException("The page size exceeds the maximum allowed value.")

    def validate_filters(
            self,
            name: Optional[str],
            description: Optional[str],
            category: Optional[str],
            created_from: Optional[datetime],
            created_to: Optional[datetime]
    ) -> None:
        for _, field_value in (
                ("name", name),
                ("description", description),
                ("category", category)
        ):
            if field_value is None:
                continue
            if len(field_value) > self._settings.max_filter_length:
                raise DocumentQueryInvalidRequestException("A filter value exceeds the maximum allowed length.")

        if created_from and created_to and created_from > created_to:
            raise DocumentQueryInvalidRequestException("The start of the date range cannot be after the end.")
