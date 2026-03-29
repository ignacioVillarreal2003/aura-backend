import logging
from typing import Optional

from app.domain.models.authenticated_user import AuthenticatedUser
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
    LlmProviderInvalidResponseException,
    LlmProviderTimeoutException,
    LlmProviderUnavailableException
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

    def _build_headers(self, authenticated_user: Optional[AuthenticatedUser] = None) -> dict:
        headers = {"X-Service-Api-Key": self._settings.service_api_key}
        if authenticated_user is not None:
            headers["X-User-Id"] = str(authenticated_user.id)
            headers["X-User-Roles"] = ",".join(authenticated_user.roles)
            headers["X-User-Permissions"] = ",".join(authenticated_user.permissions)
        return headers

    async def classify_document(
            self,
            document_name: str,
            content: str,
            authenticated_user: Optional[AuthenticatedUser] = None
    ) -> ClassifyDocumentResponse:
        logger.info(
            "Classifying document via LLM service",
            extra={"document_name": document_name}
        )

        request_body = ClassifyDocumentRequest(
            document_name=document_name,
            content=content
        )

        try:
            response = await self._http_client.post(
                url=self._settings.classify_document_url,
                json=request_body.model_dump(),
                headers=self._build_headers(authenticated_user),
                timeout=self._settings.timeout_seconds
            )

            classify_response = ClassifyDocumentResponse.model_validate(response.json())

            logger.info(
                "Document classified successfully",
                extra={
                    "document_name": document_name,
                    "type": classify_response.type.value,
                    "category": classify_response.category
                }
            )

            return classify_response

        except HttpClientTimeoutException as e:
            logger.error(
                "Timeout classifying document",
                extra={"document_name": document_name}
            )
            raise LlmProviderTimeoutException(
                f"Timeout classifying document: {document_name}"
            ) from e

        except (HttpClientConnectionException, HttpClientCircuitBreakerException) as e:
            logger.error(
                "LLM service unavailable",
                extra={"document_name": document_name}
            )
            raise LlmProviderUnavailableException(
                "LLM service is unavailable"
            ) from e

        except HttpClientException as e:
            logger.error(
                "HTTP error classifying document",
                extra={"document_name": document_name, "error": str(e)}
            )
            raise LlmProviderException(
                f"Error classifying document: {document_name}"
            ) from e

        except (ValueError, KeyError, TypeError) as e:
            logger.error(
                "Invalid response from LLM service",
                extra={"document_name": document_name, "error": str(e)}
            )
            raise LlmProviderInvalidResponseException(
                f"Invalid response from LLM service for document: {document_name}"
            ) from e

        except LlmProviderException:
            raise

        except Exception as e:
            logger.exception(
                "Unexpected error classifying document",
                extra={"document_name": document_name}
            )
            raise LlmProviderException(
                f"Unexpected error classifying document: {document_name}"
            ) from e

    async def enrich_fragment(
            self,
            content: str,
            authenticated_user: Optional[AuthenticatedUser] = None
    ) -> EnrichFragmentResponse:
        logger.info("Enriching fragment via LLM service")

        request_body = EnrichFragmentRequest(content=content)

        try:
            response = await self._http_client.post(
                url=self._settings.enrich_fragment_url,
                json=request_body.model_dump(),
                headers=self._build_headers(authenticated_user),
                timeout=self._settings.timeout_seconds
            )

            enrich_response = EnrichFragmentResponse.model_validate(response.json())

            logger.info(
                "Fragment enriched successfully",
                extra={"topics_count": len(enrich_response.topics)}
            )

            return enrich_response

        except HttpClientTimeoutException as e:
            logger.error("Timeout enriching fragment")
            raise LlmProviderTimeoutException(
                "Timeout enriching fragment"
            ) from e

        except (HttpClientConnectionException, HttpClientCircuitBreakerException) as e:
            logger.error("LLM service unavailable during fragment enrichment")
            raise LlmProviderUnavailableException(
                "LLM service is unavailable"
            ) from e

        except HttpClientException as e:
            logger.error(
                "HTTP error enriching fragment",
                extra={"error": str(e)}
            )
            raise LlmProviderException(
                "Error enriching fragment"
            ) from e

        except (ValueError, KeyError, TypeError) as e:
            logger.error(
                "Invalid response from LLM service for fragment enrichment",
                extra={"error": str(e)}
            )
            raise LlmProviderInvalidResponseException(
                "Invalid response from LLM service for fragment enrichment"
            ) from e

        except LlmProviderException:
            raise

        except Exception as e:
            logger.exception("Unexpected error enriching fragment")
            raise LlmProviderException(
                "Unexpected error enriching fragment"
            ) from e
