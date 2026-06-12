import logging
from typing import NoReturn, Optional
from fastapi import HTTPException, Request, status

from app.configuration.tracing import record_retrieved_documents, retrieval_span
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.document_context_provider.document_context_provider_request_builders import (
    build_legacy_question_retrieval_request,
)
from app.infrastructure.http.document_context_provider.document_context_provider_settings import (
    DocumentContextProviderSettings,
)
from app.infrastructure.http.document_context_provider.document_context_provider_utils import (
    calculate_question_response_max_fragments,
    parse_and_apply_limits,
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
    DocumentContextProviderTimeoutException,
    DocumentContextProviderUnauthorizedException,
    DocumentContextProviderUnavailableException,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.http.authentication_provider.request_token import get_request_token
from app.infrastructure.http.http_client.exceptions.http_client_exceptions import (
    HttpClientCircuitBreakerException,
    HttpClientConnectionException,
    HttpClientException,
    HttpClientTimeoutException,
)
from app.infrastructure.http.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)

_HTTP_ERROR_TYPES = (
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

    async def retrieve_context_fragments_by_question_request(
            self,
            authenticated_user: AuthenticatedUser,
            request: QuestionContextFragmentsRequest,
    ) -> FragmentListResponse:
        logger.info(
            "Retrieving context fragments by question (structured request).",
            extra={
                "user_id": authenticated_user.id,
                "semantic_query_count": len(request.semantic_queries),
                "bm25_query_count": len(request.bm25_queries),
                "rerank": request.rerank.enabled,
            },
        )

        if self._settings.log_payloads:
            logger.info(
                "Retrieval queries",
                extra={
                    "user_id": authenticated_user.id,
                    "semantic_queries": [q.text for q in request.semantic_queries],
                    "bm25_queries": [q.text for q in request.bm25_queries],
                },
            )

        try:
            with retrieval_span(
                    "retrieve_fragments_by_question",
                    [q.text for q in request.semantic_queries] + [q.text for q in request.bm25_queries],
            ) as span:
                response = await self._http_client.post(
                    url=self._settings.question_context_fragments_url,
                    json=request.model_dump(exclude_none=True, mode="json"),
                    headers=self._build_headers(authenticated_user),
                    timeout=self._settings.timeout_seconds,
                )
                max_fragments = calculate_question_response_max_fragments(request)
                fragments = parse_and_apply_limits(
                    raw_data=response.json(),
                    max_fragments=max_fragments,
                )
                record_retrieved_documents(span, fragments.fragments)

            logger.info(
                "Context fragments by question retrieved successfully.",
                extra={
                    "user_id": authenticated_user.id,
                    "fragments_returned": len(fragments.fragments),
                    "fragments_limit": max_fragments,
                },
            )
            self._log_fragments(fragments)
            return fragments

        except DocumentContextProviderError:
            raise
        except _HTTP_ERROR_TYPES as e:
            self._handle_http_error(e)
        except Exception as e:
            logger.exception(
                "Unexpected error retrieving context fragments by question.",
                extra={"user_id": authenticated_user.id},
            )
            raise DocumentContextProviderError(
                "Unexpected error while retrieving fragments from the external service."
            ) from e

    async def retrieve_context_fragments_by_question(
            self,
            authenticated_user: AuthenticatedUser,
            question: str,
            question_max_fragments: int,
            use_keywords: Optional[bool] = None,
            keywords: Optional[str] = None,
            keywords_max_fragments: Optional[int] = None,
            use_rerank: Optional[bool] = None,
            rerank_max_fragments: Optional[int] = None,
            chat_id: Optional[int] = None,
    ) -> FragmentListResponse:
        logger.info(
            "Retrieving context fragments by question.",
            extra={
                "user_id": authenticated_user.id,
                "use_rerank": bool(use_rerank),
                "use_keywords": bool(use_keywords),
            },
        )

        try:
            request_body = build_legacy_question_retrieval_request(
                question=question,
                question_max_fragments=question_max_fragments,
                use_keywords=use_keywords,
                keywords=keywords,
                keywords_max_fragments=keywords_max_fragments,
                use_rerank=use_rerank,
                rerank_max_fragments=rerank_max_fragments,
                chat_id=chat_id,
            )
        except Exception as e:
            logger.error(
                "Invalid question request parameters.",
                extra={"error": str(e)},
            )
            raise DocumentContextProviderError(
                f"The request parameters are invalid: {e}",
                status_code=400,
            ) from e

        return await self.retrieve_context_fragments_by_question_request(
            authenticated_user=authenticated_user,
            request=request_body,
        )

    async def retrieve_context_fragments_by_document(
            self,
            authenticated_user: AuthenticatedUser,
            document_ids: list[int],
    ) -> FragmentListResponse:
        logger.info(
            "Retrieving context fragments by document.",
            extra={
                "user_id": authenticated_user.id,
                "document_count": len(document_ids),
            },
        )

        request_body = self._build_document_request(document_ids)

        try:
            with retrieval_span(
                    "retrieve_fragments_by_document",
                    [f"document_ids: {document_ids}"],
            ) as span:
                response = await self._http_client.post(
                    url=self._settings.document_context_fragments_url,
                    json=request_body.model_dump(),
                    headers=self._build_headers(authenticated_user),
                    timeout=self._settings.timeout_seconds,
                )

                fragments = parse_and_apply_limits(
                    raw_data=response.json(),
                    max_fragments=self._settings.max_fragments_per_document_response,
                )
                record_retrieved_documents(span, fragments.fragments)

            logger.info(
                "Context fragments by document retrieved successfully.",
                extra={
                    "user_id": authenticated_user.id,
                    "document_count": len(document_ids),
                    "fragments_returned": len(fragments.fragments),
                    "fragments_limit": self._settings.max_fragments_per_document_response,
                },
            )
            self._log_fragments(fragments)
            return fragments

        except DocumentContextProviderError:
            raise
        except _HTTP_ERROR_TYPES as e:
            self._handle_http_error(e)
        except Exception as e:
            logger.exception(
                "Unexpected error retrieving context fragments by document.",
                extra={
                    "user_id": authenticated_user.id,
                    "document_count": len(document_ids),
                },
            )
            raise DocumentContextProviderError(
                "Unexpected error while retrieving fragments from the external service."
            ) from e

    def _log_fragments(self, fragments: FragmentListResponse) -> None:
        if not self._settings.log_payloads:
            return
        max_chars = self._settings.log_payload_max_chars
        for fragment in fragments.fragments:
            preview = fragment.content[:max_chars]
            if len(fragment.content) > max_chars:
                preview += f"... [+{len(fragment.content) - max_chars} chars]"
            logger.info(
                "Retrieved fragment",
                extra={
                    "fragment_id": fragment.id,
                    "document_id": fragment.document_id,
                    "document_name": fragment.document.name,
                    "fragment_index": fragment.fragment_index,
                    "fragment_chars": len(fragment.content),
                    "fragment_preview": preview,
                },
            )

    def _build_headers(
            self,
            authenticated_user: AuthenticatedUser,
    ) -> dict[str, str]:
        token = get_request_token()
        if not token:
            logger.warning(
                "No JWT available for outbound request; the downstream service will reject it.",
                extra={"user_id": authenticated_user.id},
            )
            return {}
        return {"Authorization": token}

    @staticmethod
    def _build_document_request(
            document_ids: list[int],
    ) -> DocumentsContextFragmentsRequest:
        try:
            return DocumentsContextFragmentsRequest(document_ids=document_ids)
        except Exception as e:
            logger.error(
                "Invalid document request parameters.",
                extra={"error": str(e)},
            )
            raise DocumentContextProviderError(
                f"The request parameters are invalid: {e}",
                status_code=400,
            ) from e

    @staticmethod
    def _handle_http_error(error: HttpClientException) -> NoReturn:
        if isinstance(error, HttpClientTimeoutException):
            logger.error(
                "Context service timed out.",
                extra={"error_type": type(error).__name__},
            )
            raise DocumentContextProviderTimeoutException(
                "The context service did not respond in time. Please try again later."
            ) from error

        if isinstance(error, (HttpClientConnectionException, HttpClientCircuitBreakerException)):
            logger.error(
                "Context service is unavailable.",
                extra={"error_type": type(error).__name__},
            )
            raise DocumentContextProviderUnavailableException(
                "Could not connect to the context service. Please try again later."
            ) from error

        status_code = getattr(error, "status_code", None)
        if status_code in (401, 403):
            logger.error(
                "Context service rejected the request due to an authentication failure.",
                extra={"status_code": status_code},
            )
            raise DocumentContextProviderUnauthorizedException(
                "The context service rejected the request."
            ) from error

        logger.error(
            "Context service returned an unexpected error response.",
            extra={"status_code": status_code},
        )
        raise DocumentContextProviderUnavailableException(
            f"Context service error (HTTP {status_code}). Please try again later."
        ) from error


async def get_document_context_provider(
        request: Request,
) -> DocumentContextProviderInterface:
    try:
        return request.app.state.document_context_provider
    except AttributeError as e:
        logger.error("DocumentContextProvider not found in application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document context provider service is not available",
        ) from e
