from typing import Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.application.services.processing.document_classify_service.document_classify_prompt import (
    HUMAN_PROMPT,
    SYSTEM_PROMPT,
)
from app.application.services.processing.document_classify_service.document_classify_settings import (
    DocumentClassifyServiceSettings,
)
from app.application.services.processing.document_classify_service.exceptions.document_classify_service_exceptions import (
    DocumentClassifyServiceException,
)
from app.application.services.processing.document_classify_service.interfaces.document_classify_service_interface import (
    DocumentClassifyServiceInterface,
)
from app.application.services.processing.structured_processing_service import StructuredProcessingService
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.processing.document_classify.classify_document_request import ClassifyDocumentRequest
from app.domain.dtos.processing.document_classify.classify_document_response import ClassifyDocumentResponse
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface


class DocumentClassifyService(
    StructuredProcessingService[ClassifyDocumentRequest, ClassifyDocumentResponse, ClassifyDocumentResponse],
    DocumentClassifyServiceInterface,
):
    label = "document classification"
    exception_cls = DocumentClassifyServiceException
    parsed_model = ClassifyDocumentResponse
    llm_error_message = "El modelo de lenguaje no pudo clasificar el documento."
    unexpected_error_message = "Error inesperado al clasificar el documento."

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_classify_service_settings: Optional[DocumentClassifyServiceSettings] = None,
    ) -> None:
        super().__init__(ollama_llm_facade, ollama_llm_invoker)
        self._settings = document_classify_service_settings or DocumentClassifyServiceSettings()

    def _build_messages(
            self,
            request: ClassifyDocumentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> list[BaseMessage]:
        content = self._truncate(request.content, self._settings.max_content_chars, authenticated_user.id, "document content")
        return [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=HUMAN_PROMPT.format(document_name=request.document_name, content=content)),
        ]

    def _request_log_extra(self, request: ClassifyDocumentRequest, authenticated_user: AuthenticatedUser) -> dict:
        return {
            "user_id": authenticated_user.id,
            "document_name_len": len(request.document_name),
            "content_len": len(request.content),
        }

    async def classify_document(
            self,
            classify_document_request: ClassifyDocumentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ClassifyDocumentResponse:
        return await self._generate(classify_document_request, authenticated_user)
