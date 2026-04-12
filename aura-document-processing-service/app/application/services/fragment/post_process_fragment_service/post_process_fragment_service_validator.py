from app.application.services.fragment.post_process_fragment_service.exceptions.post_process_fragment_service_exception import (
    PostProcessFragmentInvalidRequestException,
)
from app.application.services.fragment.post_process_fragment_service.post_process_fragment_service_settings import (
    PostProcessFragmentServiceSettings,
)
from app.domain.dtos.fragment.post_process_fragment.post_process_fragments_request import (
    PostProcessFragmentsRequest,
)


class PostProcessFragmentServiceValidator:
    def __init__(
            self,
            post_process_fragment_service_settings: PostProcessFragmentServiceSettings
    ) -> None:
        self._settings = post_process_fragment_service_settings

    def validate_post_process_fragments_request(
            self,
            post_process_fragments_request: PostProcessFragmentsRequest
    ) -> None:
        self._validate_document_ids(post_process_fragments_request.document_ids)

    def _validate_document_ids(
            self,
            document_ids: list[int]
    ) -> None:
        if not document_ids:
            raise PostProcessFragmentInvalidRequestException("At least one document identifier is required.")

        if len(document_ids) > self._settings.max_document_ids:
            raise PostProcessFragmentInvalidRequestException(
                "The number of document identifiers exceeds the configured limit."
            )

        for document_id in document_ids:
            if document_id is None or document_id <= 0:
                raise PostProcessFragmentInvalidRequestException("Each document identifier must be a positive integer.")

        if len(set(document_ids)) != len(document_ids):
            raise PostProcessFragmentInvalidRequestException("Document identifiers must not contain duplicates.")
