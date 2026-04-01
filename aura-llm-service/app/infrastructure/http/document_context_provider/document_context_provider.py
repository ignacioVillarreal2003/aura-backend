import logging
from typing import NoReturn, Optional
from fastapi import HTTPException, Request, status

from app.configuration.environment_variables import environment_variables
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.document_context_provider.document_context_provider_settings import (
    DocumentContextProviderSettings
)
from app.infrastructure.http.document_context_provider.dtos.documents_context_fragments_request import \
    DocumentsContextFragmentsRequest
from app.infrastructure.http.document_context_provider.dtos.fragment_list_response import FragmentListResponse
from app.infrastructure.http.document_context_provider.dtos.question_context_fragments_request import (
    QuestionContextFragmentsRequest
)
from app.infrastructure.http.document_context_provider.exceptions.document_context_provider_exception import (
    DocumentContextProviderError,
    DocumentContextProviderInvalidResponseException,
    DocumentContextProviderTimeoutException,
    DocumentContextProviderUnauthorizedException,
    DocumentContextProviderUnavailableException
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface
)
from app.infrastructure.http.http_client.exceptions.http_client_exceptions import (
    HttpClientCircuitBreakerException,
    HttpClientConnectionException,
    HttpClientException,
    HttpClientTimeoutException
)
from app.infrastructure.http.http_client.interfaces.http_client_interface import HttpClientInterface

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
            max_fragments: int,
            authenticated_user: Optional[AuthenticatedUser] = None
    ) -> FragmentListResponse:
        logger.info("Retrieving context fragments by question")

        try:
            request_body = QuestionContextFragmentsRequest(
                question=question,
                max_fragments=max_fragments,
            )
        except Exception as e:
            logger.error("Request validation failed", extra={"error": str(e)}, exc_info=True)
            raise DocumentContextProviderError(
                f"The request parameters are invalid: {e}",
                status_code=400
            ) from e

        try:
            response = await self._http_client.post(
                url=self._settings.question_context_fragments_url,
                json=request_body.model_dump(by_alias=True),
                headers=self._build_headers(authenticated_user),
                timeout=self._settings.timeout_seconds
            )

            fragments = self._parse_and_apply_limits(response.json())

            logger.info(
                "Fragments retrieved successfully by question",
                extra={"fragment_count": len(fragments.context_fragments)}
            )
            return fragments

        except DocumentContextProviderError:
            raise

        except self._HTTP_EXCEPTIONS as e:
            self._handle_http_error(e, operation="retrieve_by_question")

        except Exception as e:
            logger.exception("Unexpected error during fragment retrieval by question")
            raise DocumentContextProviderError(
                "Unexpected error while retrieving fragments from the external service."
            ) from e

    async def retrieve_context_fragments_by_document(
            self,
            document_ids: list[int],
            authenticated_user: Optional[AuthenticatedUser] = None
    ) -> FragmentListResponse:
        logger.info("Retrieving context fragments by document")

        try:
            request_body = DocumentsContextFragmentsRequest(document_ids=document_ids)
        except Exception as e:
            logger.error("Request validation failed", extra={"error": str(e)}, exc_info=True)
            raise DocumentContextProviderError(
                f"The request parameters are invalid: {e}",
                status_code=400
            ) from e

        try:
            response = await self._http_client.post(
                url=self._settings.document_context_fragments_url,
                json=request_body.model_dump(),
                headers=self._build_headers(authenticated_user),
                timeout=self._settings.timeout_seconds,
            )

            fragments = self._parse_and_apply_limits(response.json())

            logger.info(
                "Fragments retrieved successfully by document",
                extra={"document_ids": document_ids, "fragment_count": len(fragments.context_fragments)}
            )
            return fragments

        except DocumentContextProviderError:
            raise

        except self._HTTP_EXCEPTIONS as e:
            self._handle_http_error(e, operation="retrieve_by_document")

        except Exception as e:
            logger.exception("Unexpected error during fragment retrieval by document")
            raise DocumentContextProviderError(
                "Unexpected error while retrieving fragments from the external service."
            ) from e

    def _build_headers(self, authenticated_user: Optional[AuthenticatedUser] = None) -> dict[str, str]:
        headers: dict[str, str] = {"X-Service-Api-Key": environment_variables.service_api_key}
        if authenticated_user is not None:
            headers["X-User-Id"] = str(authenticated_user.id)
            headers["X-User-Email"] = str(authenticated_user.email)
            headers["X-User-Roles"] = ",".join(authenticated_user.roles)
            headers["X-User-Permissions"] = ",".join(authenticated_user.permissions)
        return headers

    def _parse_and_apply_limits(self, raw_data: dict) -> FragmentListResponse:
        try:
            response_model = FragmentListResponse.model_validate(raw_data)
            logger.debug("Response parsed successfully")
            return response_model
        except Exception as e:
            logger.error(
                "Failed to parse response",
                extra={"error_type": type(e).__name__, "error_message": str(e)},
                exc_info=True
            )
            raise DocumentContextProviderInvalidResponseException(
                "The context service returned an invalid format response."
            ) from e

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
            raise DocumentContextProviderTimeoutException(
                "The context service did not respond in time. "
                "Please try again later."
            ) from error

        if isinstance(error, (HttpClientConnectionException, HttpClientCircuitBreakerException)):
            logger.error(
                "Context service unavailable during document context operation",
                extra={"operation": operation}
            )
            raise DocumentContextProviderUnavailableException(
                "Could not connect to the context service. "
                "Please try again later."
            ) from error

        status_code = getattr(error, "status_code", None)
        if status_code == 401 or status_code == 403:
            logger.error(
                "Unauthorized access to context service",
                extra={"operation": operation, "status_code": status_code}
            )
            raise DocumentContextProviderUnauthorizedException(
                "The context service rejected the request."
            ) from error
        logger.error(
            "Unexpected HTTP error during document context operation",
            extra={"operation": operation, "status_code": status_code}
        )
        raise DocumentContextProviderUnavailableException(
            f"Context service error (HTTP {status_code}). "
            "Please try again later."
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
