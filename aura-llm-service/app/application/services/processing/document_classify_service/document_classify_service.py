import json
import logging
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from app.application.authorization.exceptions.authorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.processing.document_classify_service.document_classify_prompt import (
    HUMAN_PROMPT,
    SYSTEM_PROMPT,
)
from app.application.services.processing.document_classify_service.document_classify_settings import (
    DocumentClassifyServiceSettings,
)
from app.application.services.processing.document_classify_service.document_classify_state import DocumentClassifyState
from app.application.services.processing.document_classify_service.exceptions.document_classify_service_exceptions import (
    DocumentClassifyServiceException,
)
from app.application.services.processing.document_classify_service.interfaces.document_classify_service_interface import (
    DocumentClassifyServiceInterface,
)
from app.application.utils.llm_json_parser import parse_json_object
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.processing.document_classify.classify_document_request import ClassifyDocumentRequest
from app.domain.dtos.processing.document_classify.classify_document_response import ClassifyDocumentResponse
from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    DocumentClassifyServiceException,
    UnauthorizedException,
)


class DocumentClassifyService(DocumentClassifyServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_classify_service_settings: Optional[DocumentClassifyServiceSettings] = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._document_classify_settings = document_classify_service_settings or DocumentClassifyServiceSettings()

    async def classify_document(
            self,
            classify_document_request: ClassifyDocumentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ClassifyDocumentResponse:
        log_extra = {
            "user_id": authenticated_user.id,
            "document_name_len": len(classify_document_request.document_name),
            "content_len": len(classify_document_request.content),
        }
        logger.info("Document classification initiated", extra=log_extra)
        try:
            state = self._build_state(classify_document_request, authenticated_user)
            result = await self._run(state)
            logger.info("Document classification completed", extra=log_extra)
            return result
        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during document classification",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise DocumentClassifyServiceException("Error inesperado al clasificar el documento.") from e

    def _build_state(
            self,
            classify_document_request: ClassifyDocumentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentClassifyState:
        content = self._truncate_content(classify_document_request.content, authenticated_user.id)
        return DocumentClassifyState(
            authenticated_user=authenticated_user,
            document_name=classify_document_request.document_name,
            content=content,
        )

    async def _run(self, state: DocumentClassifyState) -> ClassifyDocumentResponse:
        raw = await self._invoke_llm(state)
        return self._parse_response(raw, state.authenticated_user.id)

    def _truncate_content(self, content: str, user_id: int) -> str:
        if len(content) <= self._document_classify_settings.max_content_chars:
            return content
        logger.info(
            "Truncating document content for classification",
            extra={
                "original_len": len(content),
                "max_chars": self._document_classify_settings.max_content_chars,
                "user_id": user_id,
            },
        )
        return content[: self._document_classify_settings.max_content_chars]

    async def _invoke_llm(self, state: DocumentClassifyState) -> str:
        user_id = state.authenticated_user.id
        llm_input = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=HUMAN_PROMPT.format(
                    document_name=state.document_name,
                    content=state.content,
                )
            ),
        ]
        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            return await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
        except LLMInvocationError as e:
            logger.warning(
                "LLM invocation failed during document classification",
                extra={"user_id": user_id, "error_type": type(e).__name__},
            )
            raise DocumentClassifyServiceException(
                "El modelo de lenguaje no pudo clasificar el documento.",
                status_code=502,
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected LLM error during document classification",
                extra={"user_id": user_id, "error_type": type(e).__name__},
            )
            raise DocumentClassifyServiceException(
                "El modelo de lenguaje no pudo clasificar el documento.",
                status_code=502,
            ) from e

    def _parse_response(self, raw: str, user_id: int) -> ClassifyDocumentResponse:
        try:
            data = parse_json_object(raw)
            return ClassifyDocumentResponse.model_validate(data)
        except (ValidationError, json.JSONDecodeError, TypeError) as e:
            logger.warning(
                "Failed to parse classification JSON from LLM",
                extra={"user_id": user_id, "error_type": type(e).__name__, "error": str(e)},
            )
            raise DocumentClassifyServiceException(
                "La respuesta del modelo no tiene el formato JSON esperado.",
                status_code=502,
            ) from e

