from typing import Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.application.services.processing.fragment_contextualize_service.exceptions.fragment_contextualize_service_exceptions import (
    FragmentContextualizeServiceException,
)
from app.application.services.processing.fragment_contextualize_service.fragment_contextualize_prompt import (
    HUMAN_PROMPT,
    SYSTEM_PROMPT,
)
from app.application.services.processing.fragment_contextualize_service.fragment_contextualize_settings import (
    FragmentContextualizeServiceSettings,
)
from app.application.services.processing.fragment_contextualize_service.interfaces.fragment_contextualize_service_interface import (
    FragmentContextualizeServiceInterface,
)
from app.application.services.processing.structured_processing_service import StructuredProcessingService
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.processing.fragment_contextualize.contextualize_fragment_request import (
    ContextualizeFragmentRequest,
)
from app.domain.dtos.processing.fragment_contextualize.contextualize_fragment_response import (
    ContextualizeFragmentResponse,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface


class FragmentContextualizeService(
    StructuredProcessingService[
        ContextualizeFragmentRequest, ContextualizeFragmentResponse, ContextualizeFragmentResponse
    ],
    FragmentContextualizeServiceInterface,
):
    label = "fragment contextualization"
    exception_cls = FragmentContextualizeServiceException
    parsed_model = ContextualizeFragmentResponse
    llm_error_message = "El modelo de lenguaje no pudo contextualizar el fragmento."
    unexpected_error_message = "Error inesperado al contextualizar el fragmento."

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            fragment_contextualize_service_settings: Optional[FragmentContextualizeServiceSettings] = None,
    ) -> None:
        super().__init__(ollama_llm_facade, ollama_llm_invoker)
        self._settings = fragment_contextualize_service_settings or FragmentContextualizeServiceSettings()

    def _build_messages(
            self,
            request: ContextualizeFragmentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> list[BaseMessage]:
        content = self._truncate(
            request.content, self._settings.max_content_chars, authenticated_user.id, "fragment content"
        )
        document_summary = self._truncate(
            request.document_summary,
            self._settings.max_document_summary_chars,
            authenticated_user.id,
            "document summary",
        )
        return [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=HUMAN_PROMPT.format(document_summary=document_summary, content=content)),
        ]

    def _request_log_extra(
            self,
            request: ContextualizeFragmentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> dict:
        return {
            "user_id": authenticated_user.id,
            "content_len": len(request.content),
            "summary_len": len(request.document_summary),
        }

    async def contextualize_fragment(
            self,
            contextualize_fragment_request: ContextualizeFragmentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ContextualizeFragmentResponse:
        return await self._generate(contextualize_fragment_request, authenticated_user)
