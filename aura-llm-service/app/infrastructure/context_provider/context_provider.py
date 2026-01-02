import logging
from typing import Any, List, Optional

from app.application.exceptions.app_exceptions import ValidationError
from app.infrastructure.context_provider.context_provider_configuration import ContextProviderConfiguration
from app.infrastructure.context_provider.dtos.fragments_by_document_request import FragmentsByDocumentRequest
from app.infrastructure.context_provider.dtos.fragments_by_question_request import FragmentsByQuestionRequest
from app.infrastructure.context_provider.dtos.fragments_response import FragmentsResponse
from app.infrastructure.context_provider.exceptions.context_provider_exception import (
    ContextRetrievalByQuestionError,
    ContextRetrievalByDocumentError
)
from app.infrastructure.context_provider.interfaces.context_provider_interface import ContextProviderInterface
from app.infrastructure.http_client.exceptions.http_client_exceptions import HttpClientError
from app.infrastructure.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)


class ContextProvider(ContextProviderInterface):
    def __init__(self,
                 http_client: HttpClientInterface,
                 retrieve_fragments_by_question_url: str,
                 retrieve_fragments_by_document_url: str,
                 configuration: Optional[ContextProviderConfiguration] = None) -> None:
        self._http_client = http_client
        self._retrieve_fragments_by_question_url = retrieve_fragments_by_question_url
        self._retrieve_fragments_by_document_url = retrieve_fragments_by_document_url
        self._configuration = configuration or ContextProviderConfiguration()

        logger.info(
            "ContextProvider initialized successfully",
            extra={
                "retrieve_fragments_by_question_url": retrieve_fragments_by_question_url,
                "retrieve_fragments_by_document_url": retrieve_fragments_by_document_url,
                "default_fragments_count": self._configuration.default_fragments_count,
                "min_fragments_count": self._configuration.min_fragments_count,
                "max_fragments_count": self._configuration.max_fragments_count,
                "max_fragment_chars": self._configuration.max_fragment_chars,
                "truncate_oversized_fragments": self._configuration.truncate_oversized_fragments,
                "max_total_fragments_in_response": self._configuration.max_total_fragments_in_response,
                "max_response_size_chars": self._configuration.max_response_size_chars
            }
        )

    @classmethod
    def with_defaults(cls,
                      http_client: HttpClientInterface,
                      retrieve_fragments_by_question_url: str,
                      retrieve_fragments_by_document_url: str,
                      default_fragments_count: int = 3,
                      min_fragments_count: int = 1,
                      max_fragments_count: int = 6,
                      max_fragment_chars: int = 10000,
                      truncate_oversized_fragments: bool = False,
                      max_total_fragments_in_response: int = 100,
                      max_response_size_chars: int = 500000) -> "ContextProvider":
        configuration = ContextProviderConfiguration(
            default_fragments_count=default_fragments_count,
            min_fragments_count=min_fragments_count,
            max_fragments_count=max_fragments_count,
            max_fragment_chars=max_fragment_chars,
            truncate_oversized_fragments=truncate_oversized_fragments,
            max_total_fragments_in_response=max_total_fragments_in_response,
            max_response_size_chars=max_response_size_chars
        )
        return cls(
            http_client=http_client,
            retrieve_fragments_by_question_url=retrieve_fragments_by_question_url,
            retrieve_fragments_by_document_url=retrieve_fragments_by_document_url,
            configuration=configuration
        )

    async def retrieve_fragments_by_question(self,
                                             question: str,
                                             fragments_count: Optional[int] = None) -> List[str]:
        self._validate_question(question)
        fragments_count = self._normalize_fragments_count(fragments_count)

        logger.info(
            "Retrieving context fragments by question",
            extra={
                "question": question,
                "fragments_count": fragments_count
            }
        )

        try:
            request_model = FragmentsByQuestionRequest(
                question=question,
                fragments_count=fragments_count
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
                url=self._retrieve_fragments_by_question_url,
                json=payload
            )

            fragments = self._parse_and_validate_response(
                data=data,
                fragments_count=fragments_count,
                error_class=ContextRetrievalByQuestionError
            )

            logger.info(
                "Fragments retrieved successfully by question",
                extra={
                    "question": question,
                    "requested_fragments": fragments_count,
                    "retrieved_fragments": len(fragments)
                }
            )

            return fragments

        except HttpClientError as e:
            logger.error(
                "HTTP communication error during fragment retrieval by question",
                extra={
                    "question": question,
                    "fragments_count": fragments_count,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise ContextRetrievalByQuestionError(
                "No se pudieron recuperar los fragmentos del servicio externo. "
                "Por favor, intente nuevamente más tarde."
            ) from e

    async def retrieve_fragments_by_document(self,
                                             document_id: int) -> List[str]:
        self._validate_document_id(document_id)

        logger.info(
            "Retrieving context fragments by document",
            extra={
                "document_id": document_id
            }
        )

        try:
            request_model = FragmentsByDocumentRequest(
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
                url=self._retrieve_fragments_by_document_url,
                json=payload
            )

            fragments = self._parse_and_validate_response(
                data=data,
                fragments_count=None,
                error_class=ContextRetrievalByDocumentError
            )

            logger.info(
                "Fragments retrieved successfully by document",
                extra={
                    "document_id": document_id,
                    "total_fragments": len(fragments),
                    "total_chars": sum(len(f) for f in fragments),
                    "avg_fragment_length": sum(len(f) for f in fragments) // len(fragments) if fragments else 0
                }
            )

            return fragments

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

    @staticmethod
    def _validate_question(question: str) -> None:
        if not question or not question.strip():
            logger.warning(
                "Question validation failed: empty or whitespace-only question",
                extra={
                    "question_repr": repr(question),
                    "question_length": len(question) if question else 0
                }
            )
            raise ValidationError(
                "La pregunta no puede estar vacía. Por favor, proporcione una pregunta válida.",
                status_code=400
            )

    def _normalize_fragments_count(self,
                                   fragments_count: Optional[int]) -> int:
        if fragments_count is None:
            logger.debug(
                "Using default fragments count",
                extra={
                    "default_value": self._configuration.default_fragments_count
                }
            )
            return self._configuration.default_fragments_count

        self._validate_fragments_count(fragments_count)
        return fragments_count

    def _validate_fragments_count(self,
                                  fragments_count: int) -> None:
        if not (self._configuration.min_fragments_count <= fragments_count <= self._configuration.max_fragments_count):
            logger.warning(
                "Fragments count validation failed: out of range",
                extra={
                    "fragments_count": fragments_count,
                    "min_fragments_count": self._configuration.min_fragments_count,
                    "max_fragments_count": self._configuration.max_fragments_count
                }
            )
            raise ValidationError(
                f"La cantidad de fragmentos debe estar entre "
                f"{self._configuration.min_fragments_count} y {self._configuration.max_fragments_count}. "
                f"Valor proporcionado: {fragments_count}.",
                status_code=400
            )

    @staticmethod
    def _validate_document_id(document_id: int) -> None:
        if document_id <= 0:
            logger.warning(
                "Document ID validation failed: non-positive integer",
                extra={
                    "document_id": document_id,
                    "value_type": type(document_id).__name__
                }
            )
            raise ValidationError(
                f"El ID del documento debe ser un número entero positivo. "
                f"Valor proporcionado: {document_id}.",
                status_code=400
            )

    def _parse_and_validate_response(self,
                                     data: Any,
                                     fragments_count: Optional[int],
                                     error_class: type[Exception]) -> List[str]:
        try:
            response_model = FragmentsResponse.model_validate(data)
            raw_fragments = response_model.fragments

            logger.debug(
                "Response parsed successfully",
                extra={
                    "raw_fragments": raw_fragments
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

        validated_fragments = self._apply_security_limits(
            fragments=raw_fragments,
            fragments_count=fragments_count
        )

        return validated_fragments

    def _apply_security_limits(self,
                               fragments: List[str],
                               fragments_count: Optional[int]) -> List[str]:
        validated_fragments: List[str] = []
        total_chars = 0
        skipped_oversized = 0
        skipped_count_limit = 0
        truncated_count = 0

        max_to_process = min(
            len(fragments),
            self._configuration.max_total_fragments_in_response
        )

        if len(fragments) > max_to_process:
            logger.warning(
                "Response exceeds maximum allowed fragments, truncating",
                extra={
                    "received_fragments": len(fragments),
                    "max_allowed": self._configuration.max_total_fragments_in_response
                }
            )

        for idx, fragment in enumerate(fragments[:max_to_process]):
            fragment_len = len(fragment)

            if fragment_len > self._configuration.max_fragment_chars:
                if self._configuration.truncate_oversized_fragments:
                    fragment = fragment[:self._configuration.max_fragment_chars]
                    truncated_count += 1

                    logger.debug(
                        "Fragment truncated due to size limit",
                        extra={
                            "fragment_index": idx,
                            "original_length": fragment_len,
                            "truncated_length": len(fragment),
                            "max_allowed": self._configuration.max_fragment_chars
                        }
                    )
                else:
                    skipped_oversized += 1

                    logger.warning(
                        "Fragment skipped due to excessive size",
                        extra={
                            "fragment_index": idx,
                            "fragment_length": fragment_len,
                            "max_allowed": self._configuration.max_fragment_chars,
                            "total_skipped": skipped_oversized
                        }
                    )
                    continue

            if total_chars + len(fragment) > self._configuration.max_response_size_chars:
                logger.warning(
                    "Total response size limit reached, stopping collection",
                    extra={
                        "fragments_collected": len(validated_fragments),
                        "total_chars_collected": total_chars,
                        "max_allowed_chars": self._configuration.max_response_size_chars
                    }
                )
                break

            if fragments_count is not None and len(validated_fragments) >= fragments_count:
                skipped_count_limit = len(fragments) - idx
                logger.debug(
                    "Requested fragment count reached",
                    extra={
                        "requested_count": fragments_count,
                        "fragments_remaining": skipped_count_limit
                    }
                )
                break

            validated_fragments.append(fragment)
            total_chars += len(fragment)

        logger.info(
            "Fragment security validation completed",
            extra={
                "raw_fragments": len(fragments),
                "validated_fragments": len(validated_fragments),
                "total_chars": total_chars,
                "skipped_oversized": skipped_oversized,
                "skipped_count_limit": skipped_count_limit,
                "truncated": truncated_count
            }
        )

        return validated_fragments

    @property
    def configuration(self) -> ContextProviderConfiguration:
        return self._configuration
