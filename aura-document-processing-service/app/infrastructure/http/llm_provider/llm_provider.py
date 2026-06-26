import json
import logging
import time
from typing import Any, Optional, TypeVar
from pydantic import BaseModel, ValidationError

from app.configuration.metrics import (
    llm_request_duration_seconds,
    llm_requests_total,
    llm_result_from_status,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.request_token import get_request_token
from app.infrastructure.http.http_client.exceptions.http_client_exceptions import (
    HttpClientCircuitBreakerException,
    HttpClientConnectionException,
    HttpClientException,
    HttpClientTimeoutException,
)
from app.infrastructure.http.http_client.interfaces.http_client_interface import HttpClientInterface
from app.infrastructure.http.llm_provider.dtos.classify_document_request import ClassifyDocumentRequest
from app.infrastructure.http.llm_provider.dtos.classify_document_response import ClassifyDocumentResponse
from app.infrastructure.http.llm_provider.dtos.contextualize_fragment_request import (
    ContextualizeFragmentRequest,
)
from app.infrastructure.http.llm_provider.dtos.contextualize_fragment_response import (
    ContextualizeFragmentResponse,
)
from app.infrastructure.http.llm_provider.dtos.extract_entities_relations_request import (
    ExtractEntitiesRelationsRequest,
)
from app.infrastructure.http.llm_provider.dtos.extract_entities_relations_response import (
    ExtractEntitiesRelationsResponse,
)
from app.infrastructure.http.llm_provider.dtos.translate_graph_query_request import (
    GraphOntology,
    TranslateGraphQueryRequest,
)
from app.infrastructure.http.llm_provider.dtos.translate_graph_query_response import (
    TranslateGraphQueryResponse,
)
from app.infrastructure.http.llm_provider.exceptions.llm_provider_exception import (
    LlmProviderException,
    LlmProviderInvalidResponseException,
)
from app.infrastructure.http.llm_provider.interfaces.llm_provider_interface import LlmProviderInterface
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
    def _build_headers() -> dict[str, str]:
        headers = {"Accept": "application/json"}
        token = get_request_token()
        if token:
            headers["Authorization"] = token
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

    def _raise_if_contextualize_payload_too_large(
            self,
            content: str,
            user_id: int
    ) -> None:
        if len(content) > self._settings.max_contextualize_content_length:
            logger.warning(
                "Fragment contextualization rejected because the content exceeds the configured limit.",
                extra={
                    "user_id": user_id,
                    "content_length": len(content),
                    "max_contextualize_content_length": self._settings.max_contextualize_content_length,
                },
            )
            raise LlmProviderException(
                "The fragment content exceeds the maximum length allowed for contextualization.",
                status_code=400,
            )

    def _raise_if_extract_payload_too_large(
            self,
            content: str,
            user_id: int,
    ) -> None:
        if len(content) > self._settings.max_extract_content_length:
            logger.warning(
                "Entity/relation extraction rejected because the content exceeds the configured limit.",
                extra={
                    "user_id": user_id,
                    "content_length": len(content),
                    "max_extract_content_length": self._settings.max_extract_content_length,
                },
            )
            raise LlmProviderException(
                "The fragment content exceeds the maximum length allowed for extraction.",
                status_code=400,
            )

    def _raise_if_translate_question_too_large(
            self,
            question: str,
            user_id: int,
    ) -> None:
        if len(question) > self._settings.max_translate_query_question_length:
            logger.warning(
                "Graph query translation rejected because the question exceeds the configured limit.",
                extra={
                    "user_id": user_id,
                    "question_length": len(question),
                    "max_translate_query_question_length":
                        self._settings.max_translate_query_question_length,
                },
            )
            raise LlmProviderException(
                "The graph query question exceeds the maximum length allowed.",
                status_code=400,
            )

    def _require_extract_url(self) -> str:
        if not self._settings.extract_entities_relations_url:
            raise LlmProviderException(
                "The LLM service URL for entity/relation extraction is not configured.",
                status_code=503,
            )
        return self._settings.extract_entities_relations_url

    def _require_translate_url(self) -> str:
        if not self._settings.translate_graph_query_url:
            raise LlmProviderException(
                "The LLM service URL for graph query translation is not configured.",
                status_code=503,
            )
        return self._settings.translate_graph_query_url

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
        start = time.perf_counter()
        try:
            result = await self._do_post_llm_json(
                url=url,
                json_body=json_body,
                timeout=timeout,
                response_model=response_model,
                authenticated_user=authenticated_user,
                operation=operation,
            )
        except LlmProviderInvalidResponseException:
            llm_requests_total.labels(operation=operation, result="invalid_response").inc()
            raise
        except LlmProviderException as e:
            llm_requests_total.labels(
                operation=operation,
                result=llm_result_from_status(getattr(e, "status_code", None)),
            ).inc()
            raise
        except Exception:
            llm_requests_total.labels(operation=operation, result="error").inc()
            raise
        else:
            llm_requests_total.labels(operation=operation, result="success").inc()
            return result
        finally:
            llm_request_duration_seconds.labels(operation=operation).observe(
                time.perf_counter() - start
            )

    async def _do_post_llm_json(
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
                headers=self._build_headers(),
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

        except HttpClientTimeoutException as e:
            logger.error(
                "The request to the LLM service timed out before a response was received.",
                extra={"user_id": user_id, "operation": operation},
            )
            raise LlmProviderException(
                "The LLM service request timed out.",
                status_code=504,
            ) from e

        except (HttpClientConnectionException, HttpClientCircuitBreakerException) as e:
            logger.error(
                "The LLM service could not be reached or is temporarily rejecting requests.",
                extra={"user_id": user_id, "operation": operation},
            )
            raise LlmProviderException(
                "The LLM service is temporarily unavailable.",
                status_code=503,
            ) from e

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
                status_code=getattr(e, "status_code", 500),
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

    async def contextualize_fragment(
            self,
            document_summary: str,
            content: str,
            authenticated_user: AuthenticatedUser,
    ) -> ContextualizeFragmentResponse:
        logger.info(
            "Sending a fragment to the LLM service for contextualization.",
            extra={"user_id": authenticated_user.id},
        )

        self._raise_if_contextualize_payload_too_large(
            content=content,
            user_id=authenticated_user.id,
        )

        try:
            contextualize_fragment_request = ContextualizeFragmentRequest(
                document_summary=document_summary,
                content=content,
            )
        except ValidationError as e:
            logger.warning(
                "Fragment contextualization request failed local validation.",
                extra={
                    "user_id": authenticated_user.id,
                    "validation_error_count": len(e.errors()),
                },
            )
            raise LlmProviderException(
                "The contextualization request is not valid.",
                status_code=400,
            ) from e

        contextualize_fragment_response = await self._post_llm_json(
            url=self._settings.contextualize_fragment_url,
            json_body=contextualize_fragment_request.model_dump(mode="json"),
            timeout=self._settings.effective_contextualize_timeout_seconds(),
            response_model=ContextualizeFragmentResponse,
            authenticated_user=authenticated_user,
            operation="contextualize_fragment",
        )

        logger.info(
            "The LLM service contextualized the fragment successfully.",
            extra={
                "user_id": authenticated_user.id,
                "context_length": len(contextualize_fragment_response.context),
            },
        )

        return contextualize_fragment_response

    async def extract_entities_relations(
            self,
            content: str,
            document_id: int,
            fragment_id: int,
            allowed_entity_types: list[str],
            allowed_relation_types: Optional[list[str]],
            authenticated_user: AuthenticatedUser,
    ) -> ExtractEntitiesRelationsResponse:
        logger.info(
            "Sending a fragment to the LLM service for entity/relation extraction.",
            extra={
                "user_id": authenticated_user.id,
                "document_id": document_id,
                "fragment_id": fragment_id,
                "content_length": len(content),
            },
        )

        url = self._require_extract_url()
        self._raise_if_extract_payload_too_large(
            content=content,
            user_id=authenticated_user.id,
        )

        try:
            request_payload = ExtractEntitiesRelationsRequest(
                content=content,
                document_id=document_id,
                fragment_id=fragment_id,
                allowed_entity_types=allowed_entity_types,
                allowed_relation_types=allowed_relation_types,
            )
        except ValidationError as e:
            logger.warning(
                "Entity/relation extraction request failed local validation.",
                extra={
                    "user_id": authenticated_user.id,
                    "document_id": document_id,
                    "fragment_id": fragment_id,
                    "validation_error_count": len(e.errors()),
                },
            )
            raise LlmProviderException(
                "The entity/relation extraction request is not valid.",
                status_code=400,
            ) from e

        response = await self._post_llm_json(
            url=url,
            json_body=request_payload.model_dump(mode="json"),
            timeout=self._settings.effective_extract_entities_relations_timeout_seconds(),
            response_model=ExtractEntitiesRelationsResponse,
            authenticated_user=authenticated_user,
            operation="extract_entities_relations",
        )

        logger.info(
            "The LLM service extracted entities and relations for a fragment.",
            extra={
                "user_id": authenticated_user.id,
                "document_id": document_id,
                "fragment_id": fragment_id,
                "entities_count": len(response.entities),
                "relations_count": len(response.relations),
            },
        )

        return response

    async def translate_graph_query(
            self,
            question: str,
            ontology: GraphOntology,
            authenticated_user: AuthenticatedUser,
    ) -> TranslateGraphQueryResponse:
        logger.info(
            "Sending a question to the LLM service for graph query translation.",
            extra={
                "user_id": authenticated_user.id,
                "question_length": len(question),
                "entity_types_count": len(ontology.entity_types),
                "relation_types_count": len(ontology.relation_types),
            },
        )

        url = self._require_translate_url()
        self._raise_if_translate_question_too_large(
            question=question,
            user_id=authenticated_user.id,
        )

        try:
            request_payload = TranslateGraphQueryRequest(
                question=question,
                ontology=ontology,
            )
        except ValidationError as e:
            logger.warning(
                "Graph query translation request failed local validation.",
                extra={
                    "user_id": authenticated_user.id,
                    "validation_error_count": len(e.errors()),
                },
            )
            raise LlmProviderException(
                "The graph query translation request is not valid.",
                status_code=400,
            ) from e

        response = await self._post_llm_json(
            url=url,
            json_body=request_payload.model_dump(mode="json"),
            timeout=self._settings.effective_translate_graph_query_timeout_seconds(),
            response_model=TranslateGraphQueryResponse,
            authenticated_user=authenticated_user,
            operation="translate_graph_query",
        )

        logger.info(
            "The LLM service translated a question to a structured graph intent.",
            extra={
                "user_id": authenticated_user.id,
                "intent": response.intent.value,
                "confidence": response.confidence,
            },
        )

        return response
