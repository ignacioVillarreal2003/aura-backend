import logging
from typing import NoReturn, Optional
from fastapi import HTTPException, Request, status

from app.infrastructure.document_context_provider.document_context_provider_settings import (
    DocumentContextProviderSettings
)
from app.infrastructure.document_context_provider.dtos.context_fragments_response import (
    ContextFragmentListResponse,
    ContextFragmentResponse
)
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
from app.infrastructure.http_client.exceptions.http_client_exceptions import (
    HttpClientCircuitBreakerException,
    HttpClientConnectionException,
    HttpClientException,
    HttpClientTimeoutException
)
from app.infrastructure.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)


class DocumentContextProvider(DocumentContextProviderInterface):
    _HTTP_EXCEPTIONS = (
        HttpClientCircuitBreakerException,
        HttpClientConnectionException,
        HttpClientException,
        HttpClientTimeoutException
    )

    def __init__(
            self,
            http_client: HttpClientInterface,
            document_context_provider_settings: Optional[DocumentContextProviderSettings] = None
    ) -> None:
        self._http_client = http_client
        self._settings = document_context_provider_settings or DocumentContextProviderSettings()

    async def retrieve_context_fragments_by_question(
            self,
            question: str,
            max_context_fragments: int,
            authorization: Optional[str] = None
    ) -> list[str]:
        logger.info("Retrieving context fragments by question")

        try:
            request_body = QuestionContextFragmentsRequest(
                question=question,
                max_context_fragments=max_context_fragments,
            )
        except Exception as e:
            logger.error("Request validation failed", extra={"error": str(e)}, exc_info=True)
            raise DocumentContextProviderError(
                f"Los parámetros de la solicitud son inválidos: {e}",
                status_code=400
            ) from e

        try:
            response = await self._http_client.post(
                url=self._settings.question_context_fragments_url,
                json=request_body.model_dump(),
                headers=self._build_headers(authorization)
            )

            fragments = self._parse_and_apply_limits(response.json())

            logger.info(
                "Fragments retrieved successfully by question",
                extra={"fragment_count": len(fragments)}
            )
            return fragments

        except DocumentContextProviderError:
            raise

        except self._HTTP_EXCEPTIONS as e:
            self._handle_http_error(e, operation="retrieve_by_question")

        except Exception as e:
            logger.exception("Unexpected error during fragment retrieval by question")
            raise DocumentContextProviderError(
                "Error inesperado al recuperar los fragmentos del servicio externo."
            ) from e

    async def retrieve_context_fragments_by_document(
            self,
            document_id: int,
            authorization: Optional[str] = None
    ) -> list[str]:
        logger.info("Retrieving context fragments by document")

        try:
            request_body = DocumentContextFragmentsRequest(document_id=document_id)
        except Exception as e:
            logger.error("Request validation failed", extra={"error": str(e)}, exc_info=True)
            raise DocumentContextProviderError(
                f"Los parámetros de la solicitud son inválidos: {e}",
                status_code=400
            ) from e

        try:
            response = await self._http_client.post(
                url=self._settings.document_context_fragments_url,
                json=request_body.model_dump(),
                headers=self._build_headers(authorization),
            )

            fragments = self._parse_and_apply_limits(response.json())

            logger.info(
                "Fragments retrieved successfully by document",
                extra={"document_id": document_id, "fragment_count": len(fragments)}
            )
            return fragments

        except DocumentContextProviderError:
            raise

        except self._HTTP_EXCEPTIONS as e:
            self._handle_http_error(e, operation="retrieve_by_document")

        except Exception as e:
            logger.exception("Unexpected error during fragment retrieval by document")
            raise DocumentContextProviderError(
                "Error inesperado al recuperar los fragmentos del servicio externo."
            ) from e

    @staticmethod
    def _build_headers(authorization: Optional[str]) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if authorization:
            headers["Authorization"] = authorization
        return headers

    def _parse_and_apply_limits(self, raw_data: dict) -> list[str]:
        try:
            response_model = ContextFragmentListResponse.model_validate(raw_data)
            fragments = response_model.context_fragments
            logger.debug("Response parsed successfully")
        except Exception as e:
            logger.error(
                "Failed to parse response",
                extra={"error_type": type(e).__name__, "error_message": str(e)},
                exc_info=True
            )
            raise DocumentContextProviderError(
                "El servicio de contexto retornó una respuesta con formato inválido."
            ) from e

        return self._apply_limits(fragments)

    def _apply_limits(self, fragments: list[ContextFragmentResponse]) -> list[str]:
        validated: list[str] = []
        total_chars = 0
        skipped_oversized = 0
        truncated_count = 0

        max_to_process = min(len(fragments), self._settings.max_fragments)

        if len(fragments) > max_to_process:
            logger.warning(
                "Response exceeds max_fragments limit — truncating",
                extra={
                    "received": len(fragments),
                    "max_fragments": self._settings.max_fragments
                }
            )

        for fragment in fragments[:max_to_process]:
            content = fragment.content

            if len(content) > self._settings.max_chars_per_fragment:
                if self._settings.truncate_oversized_fragments:
                    content = content[: self._settings.max_chars_per_fragment]
                    truncated_count += 1
                    logger.debug("Fragment truncated due to size limit")
                else:
                    skipped_oversized += 1
                    logger.warning("Fragment skipped due to excessive size")
                    continue

            if total_chars + len(content) > self._settings.max_total_chars:
                logger.warning("max_total_chars limit reached — stopping collection")
                break

            validated.append(content)
            total_chars += len(content)

        logger.info(
            "Fragment limits applied",
            extra={
                "accepted": len(validated),
                "skipped_oversized": skipped_oversized,
                "truncated": truncated_count,
                "total_chars": total_chars
            }
        )
        return validated

    def _handle_http_error(
            self,
            error: HttpClientException,
            operation: str
    ) -> NoReturn:
        if isinstance(error, HttpClientTimeoutException):
            logger.error(
                "Timeout during document context operation",
                extra={"operation": operation}
            )
            raise DocumentContextProviderError(
                "El servicio de contexto no respondió a tiempo. "
                "Por favor, intente nuevamente más tarde."
            ) from error

        if isinstance(error, HttpClientConnectionException):
            logger.error(
                "Connection error during document context operation",
                extra={"operation": operation}
            )
            raise DocumentContextProviderError(
                "No se pudo conectar al servicio de contexto. "
                "Por favor, intente nuevamente más tarde."
            ) from error

        if isinstance(error, HttpClientCircuitBreakerException):
            logger.error(
                "Circuit breaker open during document context operation",
                extra={"operation": operation}
            )
            raise DocumentContextProviderError(
                "El servicio de contexto no está disponible temporalmente. "
                "Por favor, intente nuevamente más tarde."
            ) from error

        status_code = getattr(error, "status_code", None)
        logger.error(
            "Unexpected HTTP error during document context operation",
            extra={"operation": operation, "status_code": status_code}
        )
        raise DocumentContextProviderError(
            f"Error del servicio de contexto (HTTP {status_code}). "
            "Por favor, intente nuevamente más tarde."
        ) from error


async def get_document_context_provider(request: Request) -> DocumentContextProviderInterface:
    try:
        return request.app.state.document_context_provider
    except AttributeError:
        logger.error("DocumentContextProvider not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document context provider service is not available"
        )
