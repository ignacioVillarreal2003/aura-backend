import json
import logging
from typing import Any, Optional, TypeVar
from pydantic import BaseModel, ValidationError

from app.configuration.environment_variables import environment_variables
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.http_client.http_client_exceptions import (
    HttpClientCircuitBreakerException,
    HttpClientConnectionException,
    HttpClientException,
    HttpClientTimeoutException,
)
from app.infrastructure.http.http_client.http_client_interface import HttpClientInterface
from app.infrastructure.http.llm_provider.dtos.classify_document_request import ClassifyDocumentRequest
from app.infrastructure.http.llm_provider.dtos.classify_document_response import ClassifyDocumentResponse
from app.infrastructure.http.llm_provider.dtos.enrich_fragment_request import EnrichFragmentRequest
from app.infrastructure.http.llm_provider.dtos.enrich_fragment_response import EnrichFragmentResponse
from app.infrastructure.http.llm_provider.llm_provider_exception import (
    LlmProviderException,
    LlmProviderInvalidResponseException,
)
from app.infrastructure.http.llm_provider.llm_provider_interface import LlmProviderInterface
from app.infrastructure.http.llm_provider.llm_provider_settings import LlmProviderSettings

logger = logging.getLogger(__name__)

TResponse = TypeVar("TResponse", bound=BaseModel)


class LlmProvider(LlmProviderInterface):
    def __init__(
            self,
            http_client: HttpClientInterface,
            llm_provider_settings: Optional[LlmProviderSettings] = None
    ) -> None:
        self._http_client = http_client
        self._settings = llm_provider_settings or LlmProviderSettings()

    @staticmethod
    def _build_headers(
            authenticated_user: AuthenticatedUser
    ) -> dict[str, str]:
        headers: dict[str, str] = {
            "X-Service-Api-Key": environment_variables.service_api_key,
            "Accept": "application/json",
            "X-User-Id": str(authenticated_user.id),
            "X-User-Email": str(authenticated_user.email),
            "X-User-Roles": ",".join(authenticated_user.roles),
            "X-User-Permissions": ",".join(authenticated_user.permissions),
        }
        return headers

    def _raise_if_classify_payload_too_large(
            self,
            document_name: str,
            content: str,
            user_id: int
    ) -> None:
        if len(document_name) > self._settings.max_document_name_length:
            logger.warning(
                "Document classification rejected because the document name exceeds the configured limit.",
                extra={
                    "user_id": user_id,
                    "document_name_length": len(document_name),
                    "max_document_name_length": self._settings.max_document_name_length,
                },
            )
            raise LlmProviderException(
                "The document name exceeds the maximum length allowed for classification.",
                status_code=400,
            )
        if len(content) > self._settings.max_classify_content_length:
            logger.warning(
                "Document classification rejected because the content exceeds the configured limit.",
                extra={
                    "user_id": user_id,
                    "content_length": len(content),
                    "max_classify_content_length": self._settings.max_classify_content_length,
                },
            )
            raise LlmProviderException(
                "The document content exceeds the maximum length allowed for classification.",
                status_code=400,
            )

    def _raise_if_enrich_payload_too_large(
            self,
            content: str,
            user_id: int
    ) -> None:
        if len(content) > self._settings.max_enrich_content_length:
            logger.warning(
                "Fragment enrichment rejected because the content exceeds the configured limit.",
                extra={
                    "user_id": user_id,
                    "content_length": len(content),
                    "max_enrich_content_length": self._settings.max_enrich_content_length,
                },
            )
            raise LlmProviderException(
                "The fragment content exceeds the maximum length allowed for enrichment.",
                status_code=400,
            )

    async def _post_llm_json(
            self,
            *,
            url: str,
            json_body: dict[str, Any],
            timeout: float,
            response_model: type[TResponse],
            authenticated_user: AuthenticatedUser,
            operation: str,
    ) -> TResponse:
        user_id = authenticated_user.id
        try:
            response = await self._http_client.post(
                url=url,
                json=json_body,
                headers=self._build_headers(authenticated_user),
                timeout=timeout,
            )
            try:
                payload = response.json()
            except json.JSONDecodeError as e:
                logger.error(
                    "The LLM service returned a response that is not valid JSON.",
                    extra={
                        "user_id": user_id,
                        "operation": operation,
                        "reason": "invalid_json",
                    },
                )
                raise LlmProviderInvalidResponseException(
                    "The LLM service returned a response that is not valid JSON.",
                ) from e

            try:
                return response_model.model_validate(payload)
            except ValidationError as e:
                error_count = len(e.errors())
                logger.error(
                    "The LLM service returned a response that failed schema validation.",
                    extra={
                        "user_id": user_id,
                        "operation": operation,
                        "reason": "response_validation_failed",
                        "validation_error_count": error_count,
                    },
                )
                raise LlmProviderInvalidResponseException(
                    "The LLM service returned a response that could not be validated.",
                ) from e

        except HttpClientTimeoutException:
            logger.error(
                "The request to the LLM service timed out before a response was received.",
                extra={"user_id": user_id, "operation": operation},
            )
            raise

        except (HttpClientConnectionException, HttpClientCircuitBreakerException):
            logger.error(
                "The LLM service could not be reached or is temporarily rejecting requests.",
                extra={"user_id": user_id, "operation": operation},
            )
            raise

        except HttpClientException as e:
            logger.error(
                "The LLM service returned an HTTP error.",
                extra={
                    "user_id": user_id,
                    "operation": operation,
                    "http_status_code": getattr(e, "status_code", None),
                },
            )
            raise LlmProviderException(
                "The LLM service returned an error response.",
                status_code=e.status_code,
            ) from e

        except LlmProviderException:
            raise

        except Exception as e:
            logger.exception(
                "An unexpected error occurred while calling the LLM service.",
                extra={"user_id": user_id, "operation": operation},
            )
            raise LlmProviderException(
                "An unexpected error occurred while calling the LLM service.",
                status_code=500,
            ) from e

    async def classify_document(
            self,
            document_name: str,
            content: str,
            authenticated_user: AuthenticatedUser
    ) -> ClassifyDocumentResponse:
        logger.info(
            "Sending a document to the LLM service for classification.",
            extra={"user_id": authenticated_user.id},
        )

        self._raise_if_classify_payload_too_large(
            document_name=document_name,
            content=content,
            user_id=authenticated_user.id,
        )

        try:
            classify_document_request = ClassifyDocumentRequest(
                document_name=document_name,
                content=content,
            )
        except ValidationError as e:
            logger.warning(
                "Document classification request failed local validation.",
                extra={
                    "user_id": authenticated_user.id,
                    "validation_error_count": len(e.errors()),
                },
            )
            raise LlmProviderException(
                "The classification request is not valid.",
                status_code=400,
            ) from e

        classify_document_response = await self._post_llm_json(
            url=self._settings.classify_document_url,
            json_body=classify_document_request.model_dump(mode="json"),
            timeout=self._settings.effective_classify_timeout_seconds(),
            response_model=ClassifyDocumentResponse,
            authenticated_user=authenticated_user,
            operation="classify_document",
        )

        logger.info(
            "The LLM service classified the document successfully.",
            extra={
                "user_id": authenticated_user.id,
                "type": classify_document_response.type.value,
                "category": classify_document_response.category,
            },
        )

        return classify_document_response

    async def enrich_fragment(
            self,
            content: str,
            authenticated_user: AuthenticatedUser,
    ) -> EnrichFragmentResponse:
        logger.info(
            "Sending a fragment to the LLM service for enrichment.",
            extra={"user_id": authenticated_user.id},
        )

        self._raise_if_enrich_payload_too_large(
            content=content,
            user_id=authenticated_user.id,
        )

        try:
            enrich_fragment_request = EnrichFragmentRequest(content=content)
        except ValidationError as e:
            logger.warning(
                "Fragment enrichment request failed local validation.",
                extra={
                    "user_id": authenticated_user.id,
                    "validation_error_count": len(e.errors()),
                },
            )
            raise LlmProviderException(
                "The enrichment request is not valid.",
                status_code=400,
            ) from e

        enrich_fragment_response = await self._post_llm_json(
            url=self._settings.enrich_fragment_url,
            json_body=enrich_fragment_request.model_dump(mode="json"),
            timeout=self._settings.effective_enrich_timeout_seconds(),
            response_model=EnrichFragmentResponse,
            authenticated_user=authenticated_user,
            operation="enrich_fragment",
        )

        logger.info(
            "The LLM service enriched the fragment successfully.",
            extra={
                "user_id": authenticated_user.id,
                "topics_count": len(enrich_fragment_response.topics),
            },
        )

        return enrich_fragment_response
