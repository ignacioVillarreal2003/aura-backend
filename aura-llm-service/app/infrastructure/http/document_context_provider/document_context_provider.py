import logging
from typing import Any, NoReturn, Optional

from fastapi import HTTPException, Request, status

from app.configuration.environment_variables import environment_variables
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.document_context_provider.document_context_provider_settings import (
    DocumentContextProviderSettings,
)
from app.infrastructure.http.document_context_provider.document_context_provider_validator import (
    DocumentContextProviderValidator,
)
from app.infrastructure.http.document_context_provider.dtos.documents_context_fragments_request import (
    DocumentsContextFragmentsRequest,
)
from app.infrastructure.http.document_context_provider.dtos.fragment_list_response import FragmentListResponse
from app.infrastructure.http.document_context_provider.dtos.question_context_fragments_request import (
    QuestionContextFragmentsRequest,
)
from app.infrastructure.http.document_context_provider.exceptions.document_context_provider_exception import (
    DocumentContextProviderError,
    DocumentContextProviderInvalidResponseException,
    DocumentContextProviderTimeoutException,
    DocumentContextProviderUnauthorizedException,
    DocumentContextProviderUnavailableException,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.http.http_client.exceptions.http_client_exceptions import (
    HttpClientCircuitBreakerException,
    HttpClientConnectionException,
    HttpClientException,
    HttpClientTimeoutException,
)
from app.infrastructure.http.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)

_HTTP_ERRORS = (
    HttpClientCircuitBreakerException,
    HttpClientConnectionException,
    HttpClientException,
    HttpClientTimeoutException,
)


class DocumentContextProvider(DocumentContextProviderInterface):
    def __init__(
            self,
            http_client: HttpClientInterface,
            document_context_provider_settings: Optional[DocumentContextProviderSettings] = None,
    ) -> None:
        self._http_client = http_client
        self._settings = document_context_provider_settings or DocumentContextProviderSettings()
        self._validator = DocumentContextProviderValidator(self._settings)

    async def retrieve_context_fragments_by_question(
            self,
            question: str,
            max_fragments: int,
            authenticated_user: Optional[AuthenticatedUser] = None,
    ) -> FragmentListResponse:
        self._validator.validate_question(question)
        self._validator.validate_max_fragments(max_fragments)

        op = "retrieve_by_question"
        logger.info(
            "Handling document context request by question",
            extra=self._log_extra(op, authenticated_user, question_len=len(question)),
        )

        request_body = self._build_question_request(question, max_fragments)

        try:
            response = await self._http_client.post(
                url=self._settings.question_context_fragments_url,
                json=request_body.model_dump(),
                headers=self._build_headers(authenticated_user),
                timeout=self._settings.timeout_seconds,
            )
            fragments = self._parse_and_apply_limits(response.json())
            logger.info(
                "Document context by question completed",
                extra=self._log_extra(
                    op, authenticated_user,
                    question_len=len(question),
                    fragment_count=len(fragments.fragments),
                ),
            )
            return fragments

        except DocumentContextProviderError:
            raise
        except _HTTP_ERRORS as e:
            self._handle_http_error(e, operation=op)
        except Exception:
            logger.exception(
                "Unexpected error during fragment retrieval by question",
                extra=self._log_extra(op, authenticated_user),
            )
            raise DocumentContextProviderError(
                "Unexpected error while retrieving fragments from the external service."
            )

    async def retrieve_context_fragments_by_document(
            self,
            document_ids: list[int],
            authenticated_user: Optional[AuthenticatedUser] = None,
    ) -> FragmentListResponse:
        self._validator.validate_document_ids(document_ids)

        op = "retrieve_by_document"
        logger.info(
            "Handling document context request by documents",
            extra=self._log_extra(op, authenticated_user, document_id_count=len(document_ids)),
        )

        request_body = self._build_document_request(document_ids)

        try:
            response = await self._http_client.post(
                url=self._settings.document_context_fragments_url,
                json=request_body.model_dump(),
                headers=self._build_headers(authenticated_user),
                timeout=self._settings.timeout_seconds,
            )
            fragments = self._parse_and_apply_limits(response.json())
            logger.info(
                "Document context by documents completed",
                extra=self._log_extra(
                    op, authenticated_user,
                    document_id_count=len(document_ids),
                    fragment_count=len(fragments.fragments),
                ),
            )
            return fragments

        except DocumentContextProviderError:
            raise
        except _HTTP_ERRORS as e:
            self._handle_http_error(e, operation=op)
        except Exception:
            logger.exception(
                "Unexpected error during fragment retrieval by document",
                extra=self._log_extra(op, authenticated_user, document_id_count=len(document_ids)),
            )
            raise DocumentContextProviderError(
                "Unexpected error while retrieving fragments from the external service."
            )

    @staticmethod
    def _log_extra(
        operation: str,
        authenticated_user: Optional[AuthenticatedUser] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        extra: dict[str, Any] = {"operation": operation, **kwargs}
        if authenticated_user is not None:
            extra["user_id"] = authenticated_user.id
        return extra

    def _build_headers(self, authenticated_user: Optional[AuthenticatedUser] = None) -> dict[str, str]:
        headers: dict[str, str] = {"X-Service-Api-Key": environment_variables.service_api_key}
        if authenticated_user is not None:
            headers["X-User-Id"] = str(authenticated_user.id)
            headers["X-User-Email"] = str(authenticated_user.email)
            headers["X-User-Roles"] = ",".join(authenticated_user.roles)
            headers["X-User-Permissions"] = ",".join(authenticated_user.permissions)
        return headers

    @staticmethod
    def _build_question_request(question: str, max_fragments: int) -> QuestionContextFragmentsRequest:
        try:
            return QuestionContextFragmentsRequest(question=question, max_fragments=max_fragments)
        except Exception as e:
            logger.error("Question request DTO validation failed", extra={"error": str(e)}, exc_info=True)
            raise DocumentContextProviderError(
                f"The request parameters are invalid: {e}",
                status_code=400,
            ) from e

    @staticmethod
    def _build_document_request(document_ids: list[int]) -> DocumentsContextFragmentsRequest:
        try:
            return DocumentsContextFragmentsRequest(document_ids=document_ids)
        except Exception as e:
            logger.error("Document request DTO validation failed", extra={"error": str(e)}, exc_info=True)
            raise DocumentContextProviderError(
                f"The request parameters are invalid: {e}",
                status_code=400,
            ) from e

    def _parse_and_apply_limits(self, raw_data: dict) -> FragmentListResponse:
        try:
            response_model = FragmentListResponse.model_validate(raw_data)
        except Exception as e:
            logger.error(
                "Failed to parse response from context service",
                extra={"error_type": type(e).__name__, "error_message": str(e)},
                exc_info=True,
            )
            raise DocumentContextProviderInvalidResponseException(
                "The context service returned an invalid format response."
            ) from e

        limited = self._validator.apply_response_char_limits(response_model.fragments)
        logger.debug(
            "Response parsed and limits applied",
            extra={"fragment_count": len(limited)},
        )
        return FragmentListResponse(fragments=limited)

    def _handle_http_error(self, error: HttpClientException, operation: str) -> NoReturn:
        if isinstance(error, HttpClientTimeoutException):
            logger.error(
                "Timeout during document context operation",
                extra={"operation": operation},
            )
            raise DocumentContextProviderTimeoutException(
                "The context service did not respond in time. Please try again later."
            ) from error

        if isinstance(error, (HttpClientConnectionException, HttpClientCircuitBreakerException)):
            logger.error(
                "Context service unavailable during document context operation",
                extra={"operation": operation},
            )
            raise DocumentContextProviderUnavailableException(
                "Could not connect to the context service. Please try again later."
            ) from error

        status_code = getattr(error, "status_code", None)
        if status_code in (401, 403):
            logger.error(
                "Unauthorized access to context service",
                extra={"operation": operation, "status_code": status_code},
            )
            raise DocumentContextProviderUnauthorizedException(
                "The context service rejected the request."
            ) from error

        logger.error(
            "Unexpected HTTP error during document context operation",
            extra={"operation": operation, "status_code": status_code},
        )
        raise DocumentContextProviderUnavailableException(
            f"Context service error (HTTP {status_code}). Please try again later."
        ) from error

async def get_document_context_provider(request: Request) -> DocumentContextProviderInterface:
    try:
        return request.app.state.document_context_provider
    except AttributeError:
        logger.error("DocumentContextProvider not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document context provider service is not available",
        )