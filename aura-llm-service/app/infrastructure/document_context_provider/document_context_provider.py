import logging
from typing import Any, List, Optional

from app.application.exceptions.app_exceptions import ValidationError
from app.infrastructure.document_context_provider.document_context_provider_configuration import (
    DocumentContextProviderConfiguration
)
from app.infrastructure.document_context_provider.dtos.context_fragments_by_document_request import (
    ContextFragmentsByDocumentRequest
)
from app.infrastructure.document_context_provider.dtos.context_fragments_by_question_request import (
    ContextFragmentsByQuestionRequest
)
from app.infrastructure.document_context_provider.dtos.fragments_response import FragmentsResponse
from app.infrastructure.document_context_provider.exceptions.context_provider_exception import (
    ContextRetrievalByQuestionError,
    ContextRetrievalByDocumentError
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
                 retrieve_context_fragments_by_question_url: str,
                 retrieve_context_fragments_by_document_url: str,
                 configuration: Optional[DocumentContextProviderConfiguration] = None) -> None:
        self._http_client = http_client
        self._retrieve_context_fragments_by_question_url = retrieve_context_fragments_by_question_url
        self._retrieve_context_fragments_by_document_url = retrieve_context_fragments_by_document_url
        self._configuration = configuration or DocumentContextProviderConfiguration()

        logger.info(
            "ContextProvider initialized successfully",
            extra={
                "retrieve_context_fragments_by_question_url": retrieve_context_fragments_by_question_url,
                "retrieve_context_fragments_by_document_url": retrieve_context_fragments_by_document_url,
                "max_fragment_chars": self._configuration.max_fragment_chars,
                "truncate_oversized_fragments": self._configuration.truncate_oversized_fragments,
                "max_total_fragments_in_response": self._configuration.max_total_fragments_in_response,
                "max_response_size_chars": self._configuration.max_response_size_chars
            }
        )

    @classmethod
    def create(cls,
               http_client: HttpClientInterface,
               retrieve_context_fragments_by_question_url: str,
               retrieve_context_fragments_by_document_url: str,
               max_fragment_chars: Optional[int] = None,
               truncate_oversized_fragments: Optional[bool] = None,
               max_total_fragments_in_response: Optional[int] = None,
               max_response_size_chars: Optional[int] = None) -> "DocumentContextProvider":
        config_kwargs = {}

        if max_fragment_chars is not None:
            config_kwargs['max_fragment_chars'] = max_fragment_chars
        if truncate_oversized_fragments is not None:
            config_kwargs['truncate_oversized_fragments'] = truncate_oversized_fragments
        if max_total_fragments_in_response is not None:
            config_kwargs['max_total_fragments_in_response'] = max_total_fragments_in_response
        if max_response_size_chars is not None:
            config_kwargs['max_response_size_chars'] = max_response_size_chars

        configuration = DocumentContextProviderConfiguration(**config_kwargs)

        return cls(
            http_client=http_client,
            retrieve_context_fragments_by_question_url=retrieve_context_fragments_by_question_url,
            retrieve_context_fragments_by_document_url=retrieve_context_fragments_by_document_url,
            configuration=configuration
        )

    async def retrieve_context_fragments_by_question(self,
                                                     question: str,
                                                     max_context_fragments_count: int) -> List[str]:
        logger.info(
            "Retrieving context fragments by question",
            extra={
                "question": question,
                "max_context_fragments_count": max_context_fragments_count
            }
        )

        try:
            request_model = ContextFragmentsByQuestionRequest(
                question=question,
                max_context_fragments_count=max_context_fragments_count
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

        payload = request_model.model_dump()

        try:
            data = await self._http_client.post(
                url=self._retrieve_context_fragments_by_question_url,
                json=payload
            )

            context_fragments = self._parse_and_validate_response(
                data=data,
                max_context_fragments_count=max_context_fragments_count,
                error_class=ContextRetrievalByQuestionError
            )

            logger.info(
                "Fragments retrieved successfully by question",
                extra={
                    "question": question,
                    "max_context_fragments_count": max_context_fragments_count,
                    "retrieved_context_fragments": len(context_fragments)
                }
            )

            return context_fragments

        except HttpClientError as e:
            logger.error(
                "HTTP communication error during fragment retrieval by question",
                extra={
                    "question": question,
                    "max_context_fragments_count": max_context_fragments_count,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise ContextRetrievalByQuestionError(
                "No se pudieron recuperar los fragmentos del servicio externo. Por favor, intente nuevamente más tarde."
            ) from e

    async def retrieve_context_fragments_by_document(self,
                                                     document_id: int) -> List[str]:
        logger.info(
            "Retrieving context fragments by document",
            extra={
                "document_id": document_id
            }
        )

        try:
            request_model = ContextFragmentsByDocumentRequest(
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
                f"El ID del documento es inválido: {str(e)}",
                status_code=400
            ) from e

        payload = request_model.model_dump()

        try:
            data = await self._http_client.post(
                url=self._retrieve_context_fragments_by_document_url,
                json=payload
            )

            context_fragments = self._parse_and_validate_response(
                data=data,
                max_context_fragments_count=None,
                error_class=ContextRetrievalByDocumentError
            )

            logger.info(
                "Fragments retrieved successfully by document",
                extra={
                    "document_id": document_id,
                    "total_context_fragments": len(context_fragments)
                }
            )

            return context_fragments

        except HttpClientError as e:
            logger.error(
                "HTTP communication error during fragment retrieval by document",
                extra={
                    "document_id": document_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise ContextRetrievalByDocumentError(
                f"No se pudieron recuperar los fragmentos del documento {document_id}. "
                f"Por favor, verifique que el documento exista e intente nuevamente."
            ) from e

    def _parse_and_validate_response(self,
                                     data: Any,
                                     max_context_fragments_count: Optional[int],
                                     error_class: type[Exception]) -> List[str]:
        try:
            response_model = FragmentsResponse.model_validate(data)
            raw_context_fragments = response_model.context_fragments

            logger.debug(
                "Response parsed successfully",
                extra={
                    "raw_context_fragments": raw_context_fragments
                }
            )

        except Exception as e:
            logger.error(
                "Failed to parse response",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "data_type": type(data).__name__
                },
                exc_info=True
            )
            raise error_class(
                "El servicio de contexto retornó una respuesta con formato inválido. "
                "No se pudo procesar la estructura de datos recibida."
            ) from e

        validated_context_fragments = self._apply_security_limits(
            context_fragments=raw_context_fragments,
            max_context_fragments_count=max_context_fragments_count
        )

        return validated_context_fragments

    def _apply_security_limits(self,
                               context_fragments: List[str],
                               max_context_fragments_count: Optional[int]) -> List[str]:
        validated_context_fragments: List[str] = []
        total_chars = 0
        skipped_oversized = 0
        skipped_count_limit = 0
        truncated_count = 0

        max_to_process = min(
            len(context_fragments),
            self._configuration.max_total_fragments_in_response
        )

        if len(context_fragments) > max_to_process:
            logger.warning(
                "Response exceeds maximum allowed fragments, truncating",
                extra={
                    "received_fragments": len(context_fragments),
                    "max_allowed": self._configuration.max_total_fragments_in_response
                }
            )

        for idx, context_fragment in enumerate(context_fragments[:max_to_process]):
            context_fragment_len = len(context_fragment)

            if context_fragment_len > self._configuration.max_fragment_chars:
                if self._configuration.truncate_oversized_fragments:
                    context_fragment = context_fragment[:self._configuration.max_fragment_chars]
                    truncated_count += 1

                    logger.debug(
                        "Fragment truncated due to size limit",
                        extra={
                            "fragment_index": idx,
                            "original_length": context_fragment_len,
                            "truncated_length": len(context_fragment),
                            "max_allowed": self._configuration.max_fragment_chars
                        }
                    )
                else:
                    skipped_oversized += 1

                    logger.warning(
                        "Fragment skipped due to excessive size",
                        extra={
                            "fragment_index": idx,
                            "fragment_length": context_fragment_len,
                            "max_allowed": self._configuration.max_fragment_chars,
                            "total_skipped": skipped_oversized
                        }
                    )
                    continue

            if total_chars + len(context_fragment) > self._configuration.max_response_size_chars:
                logger.warning(
                    "Total response size limit reached, stopping collection",
                    extra={
                        "fragments_collected": len(validated_context_fragments),
                        "total_chars_collected": total_chars,
                        "max_allowed_chars": self._configuration.max_response_size_chars
                    }
                )
                break

            if max_context_fragments_count is not None and len(
                    validated_context_fragments) >= max_context_fragments_count:
                skipped_count_limit = len(context_fragments) - idx
                logger.debug(
                    "Requested fragment count reached",
                    extra={
                        "requested_count": max_context_fragments_count,
                        "fragments_remaining": skipped_count_limit
                    }
                )
                break

            validated_context_fragments.append(context_fragment)
            total_chars += len(context_fragment)

        logger.info(
            "Fragment security validation completed",
            extra={
                "raw_fragments": len(context_fragments),
                "validated_fragments": len(validated_context_fragments),
                "total_chars": total_chars,
                "skipped_oversized": skipped_oversized,
                "skipped_count_limit": skipped_count_limit,
                "truncated": truncated_count
            }
        )

        return validated_context_fragments
