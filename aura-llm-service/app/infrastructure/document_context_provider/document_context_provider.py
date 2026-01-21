import logging
from typing import List, Optional

from app.application.exceptions.app_exceptions import ValidationError
from app.infrastructure.document_context_provider.document_context_provider_configuration import (
    DocumentContextProviderConfiguration
)
from app.infrastructure.document_context_provider.document_context_provider_response_validator import \
    DocumentContextProviderResponseValidator
from app.infrastructure.document_context_provider.dtos.document_context_fragments_request import (
    DocumentContextFragmentsRequest
)
from app.infrastructure.document_context_provider.dtos.question_context_fragments_request import (
    QuestionContextFragmentsRequest
)
from app.infrastructure.document_context_provider.exceptions.document_context_provider_exception import (
    DocumentContextProviderError
)
from app.infrastructure.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface
)
from app.infrastructure.http_client.exceptions.http_client_exceptions import HttpClientError
from app.infrastructure.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)


class DocumentContextProvider(DocumentContextProviderInterface):
    def __init__(self,
                 http_client: HttpClientInterface,
                 question_context_fragments_url: str,
                 document_context_fragments_url: str,
                 document_context_provider_configuration: Optional[
                     DocumentContextProviderConfiguration] = None) -> None:
        self._http_client = http_client
        self._question_context_fragments_url = question_context_fragments_url
        self._document_context_fragments_url = document_context_fragments_url
        self._document_context_provider_configuration = document_context_provider_configuration or DocumentContextProviderConfiguration()

        self._document_context_provider_response_validator = DocumentContextProviderResponseValidator(
            document_context_provider_configuration=self._document_context_provider_configuration
        )

        logger.info("ContextProvider initialized successfully")

    @classmethod
    def create(cls,
               http_client: HttpClientInterface,
               question_context_fragments_url: str,
               document_context_fragments_url: str,
               max_chars_per_fragment: Optional[int] = None,
               truncate_fragments_exceeding_max_chars: Optional[bool] = None,
               max_fragments_total: Optional[int] = None,
               max_total_chars: Optional[int] = None) -> "DocumentContextProvider":
        config_kwargs = {}

        if max_chars_per_fragment is not None:
            config_kwargs['max_chars_per_fragment'] = max_chars_per_fragment
        if truncate_fragments_exceeding_max_chars is not None:
            config_kwargs['truncate_fragments_exceeding_max_chars'] = truncate_fragments_exceeding_max_chars
        if max_fragments_total is not None:
            config_kwargs['max_fragments_total'] = max_fragments_total
        if max_total_chars is not None:
            config_kwargs['max_total_chars'] = max_total_chars

        document_context_provider_configuration = DocumentContextProviderConfiguration(**config_kwargs)

        return cls(
            http_client=http_client,
            question_context_fragments_url=question_context_fragments_url,
            document_context_fragments_url=document_context_fragments_url,
            document_context_provider_configuration=document_context_provider_configuration
        )

    async def retrieve_context_fragments_by_question(self,
                                                     question: str,
                                                     max_context_fragments: int) -> List[str]:
        logger.info("Retrieving context fragments by question")

        try:
            question_context_fragments_request = QuestionContextFragmentsRequest(
                question=question,
                max_context_fragments=max_context_fragments
            )
        except Exception as e:
            logger.error(
                "Request validation failed",
                extra={
                    "error": str(e)
                },
                exc_info=True
            )
            raise ValidationError(
                f"Los parámetros de la solicitud son inválidos: {str(e)}",
                status_code=400
            ) from e

        question_context_fragments_payload = question_context_fragments_request.model_dump()

        try:
            context_fragments_response = await self._http_client.post(
                url=self._question_context_fragments_url,
                json=question_context_fragments_payload
            )

            context_fragments = self._document_context_provider_response_validator.validate_and_parse_response(
                context_fragments_response=context_fragments_response
            )

            logger.info("Fragments retrieved successfully by question")

            return context_fragments

        except HttpClientError as e:
            logger.error(
                "HTTP communication error during fragment retrieval by question",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise DocumentContextProviderError(
                "No se pudieron recuperar los fragmentos del servicio externo. Por favor, intente nuevamente más tarde."
            ) from e

    async def retrieve_context_fragments_by_document(self,
                                                     document_id: int) -> List[str]:
        logger.info("Retrieving context fragments by document")

        try:
            document_context_fragments_request = DocumentContextFragmentsRequest(
                document_id=document_id
            )
        except Exception as e:
            logger.error(
                "Request validation failed",
                extra={
                    "error": str(e)
                },
                exc_info=True
            )
            raise ValidationError(
                f"Los parámetros de la solicitud son inválidos: {str(e)}",
                status_code=400
            ) from e

        document_context_fragments_payload = document_context_fragments_request.model_dump()

        try:
            context_fragments_response = await self._http_client.post(
                url=self._document_context_fragments_url,
                json=document_context_fragments_payload
            )

            context_fragments = self._document_context_provider_response_validator.validate_and_parse_response(
                context_fragments_response=context_fragments_response
            )

            logger.info("Fragments retrieved successfully by document")

            return context_fragments


        except HttpClientError as e:
            logger.error(
                "HTTP communication error during fragment retrieval by document",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise DocumentContextProviderError(
                "No se pudieron recuperar los fragmentos del servicio externo. Por favor, intente nuevamente más tarde."
            ) from e
