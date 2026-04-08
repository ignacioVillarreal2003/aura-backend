import logging
from typing import Optional

from app.configuration.environment_variables import environment_variables
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.http_client.exceptions.http_client_exceptions import (
    HttpClientCircuitBreakerException,
    HttpClientConnectionException,
    HttpClientException,
    HttpClientTimeoutException
)
from app.infrastructure.http.http_client.interfaces.http_client_interface import HttpClientInterface
from app.infrastructure.http.llm_provider.dtos.classify_document_request import ClassifyDocumentRequest
from app.infrastructure.http.llm_provider.dtos.classify_document_response import ClassifyDocumentResponse
from app.infrastructure.http.llm_provider.dtos.enrich_fragment_request import EnrichFragmentRequest
from app.infrastructure.http.llm_provider.dtos.enrich_fragment_response import EnrichFragmentResponse
from app.infrastructure.http.llm_provider.exceptions.llm_provider_exception import (
    LlmProviderException,
    LlmProviderInvalidResponseException
)
from app.infrastructure.http.llm_provider.interfaces.llm_provider_interface import LlmProviderInterface
from app.infrastructure.http.llm_provider.llm_provider_settings import LlmProviderSettings

logger = logging.getLogger(__name__)


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
    ) -> dict:
        headers = {"X-Service-Api-Key": environment_variables.service_api_key}
        if authenticated_user is not None:
            headers["X-User-Id"] = str(authenticated_user.id)
            headers["X-User-Email"] = str(authenticated_user.email)
            headers["X-User-Roles"] = ",".join(authenticated_user.roles)
            headers["X-User-Permissions"] = ",".join(authenticated_user.permissions)
        return headers

    async def classify_document(
            self,
            document_name: str,
            content: str,
            authenticated_user: AuthenticatedUser
    ) -> ClassifyDocumentResponse:
        logger.info(
            "Sending a document to the LLM service for classification.",
            extra={
                "user_id": authenticated_user.id
            }
        )

        classify_document_request = ClassifyDocumentRequest(
            document_name=document_name,
            content=content
        )

        try:
            response = await self._http_client.post(
                url=self._settings.classify_document_url,
                json=classify_document_request.model_dump(),
                headers=self._build_headers(authenticated_user),
                timeout=self._settings.timeout_seconds
            )

            classify_document_response = ClassifyDocumentResponse.model_validate(response.json())

            logger.info(
                "The LLM service classified the document successfully.",
                extra={
                    "user_id": authenticated_user.id,
                    "type": classify_document_response.type.value,
                    "category": classify_document_response.category
                }
            )

            return classify_document_response

        except HttpClientTimeoutException:
            logger.error(
                "The request to classify a document timed out before the LLM service responded.",
                extra={
                    "user_id": authenticated_user.id
                }
            )
            raise

        except (HttpClientConnectionException, HttpClientCircuitBreakerException):
            logger.error(
                "The LLM service could not be reached or is temporarily rejecting requests.",
                extra={
                    "user_id": authenticated_user.id
                }
            )
            raise

        except HttpClientException as e:
            logger.error(
                "The LLM service returned an HTTP error while classifying a document.",
                extra={
                    "user_id": authenticated_user.id,
                    "http_status_code": getattr(e, "status_code", None)
                }
            )
            raise

        except (
                ValueError,
                KeyError,
                TypeError
        ) as e:
            logger.error(
                "The LLM service returned a response that could not be validated for classification.",
                extra={
                    "user_id": authenticated_user.id,
                    "reason": "response_validation_failed"
                }
            )
            raise LlmProviderInvalidResponseException(
                "The LLM service returned a response that could not be validated.",
            ) from e

        except LlmProviderException:
            raise

        except Exception as e:
            logger.exception(
                "An unexpected error occurred while classifying a document through the LLM service.",
                extra={
                    "user_id": authenticated_user.id
                }
            )
            raise LlmProviderException(
                "An unexpected error occurred while classifying the document.",
                status_code=500
            ) from e

    async def enrich_fragment(
            self,
            content: str,
            authenticated_user: AuthenticatedUser,
    ) -> EnrichFragmentResponse:
        logger.info(
            "Sending a fragment to the LLM service for enrichment.",
            extra={
                "user_id": authenticated_user.id
            }
        )

        enrich_fragment_request = EnrichFragmentRequest(
            content=content
        )

        try:
            response = await self._http_client.post(
                url=self._settings.enrich_fragment_url,
                json=enrich_fragment_request.model_dump(),
                headers=self._build_headers(authenticated_user),
                timeout=self._settings.timeout_seconds
            )

            enrich_fragment_response = EnrichFragmentResponse.model_validate(response.json())

            logger.info(
                "The LLM service enriched the fragment successfully.",
                extra={
                    "user_id": authenticated_user.id,
                    "topics_count": len(enrich_fragment_response.topics)
                }
            )

            return enrich_fragment_response

        except HttpClientTimeoutException:
            logger.error(
                "The request to enrich a fragment timed out before the LLM service responded.",
                extra={
                    "user_id": authenticated_user.id
                }
            )
            raise

        except (HttpClientConnectionException, HttpClientCircuitBreakerException):
            logger.error(
                "The LLM service could not be reached or is temporarily rejecting requests.",
                extra={
                    "user_id": authenticated_user.id
                }
            )
            raise

        except HttpClientException as e:
            logger.error(
                "The LLM service returned an HTTP error while enriching a fragment.",
                extra={
                    "user_id": authenticated_user.id,
                    "http_status_code": getattr(e, "status_code", None)
                }
            )
            raise

        except (
                ValueError,
                KeyError,
                TypeError
        ) as e:
            logger.error(
                "The LLM service returned a response that could not be validated for fragment enrichment.",
                extra={
                    "user_id": authenticated_user.id,
                    "reason": "response_validation_failed"
                }
            )
            raise LlmProviderInvalidResponseException(
                "The LLM service returned a response that could not be validated."
            ) from e

        except LlmProviderException:
            raise

        except Exception as e:
            logger.exception(
                "An unexpected error occurred while enriching a fragment through the LLM service.",
                extra={
                    "user_id": authenticated_user.id
                }
            )
            raise LlmProviderException(
                "An unexpected error occurred while enriching the fragment.",
                status_code=500
            ) from e
