from typing import Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.application.services.processing.fragment_enrich_service.exceptions.fragment_enrich_service_exceptions import (
    FragmentEnrichServiceException,
)
from app.application.services.processing.fragment_enrich_service.fragment_enrich_prompt import (
    HUMAN_PROMPT,
    SYSTEM_PROMPT,
)
from app.application.services.processing.fragment_enrich_service.fragment_enrich_settings import (
    FragmentEnrichServiceSettings,
)
from app.application.services.processing.fragment_enrich_service.interfaces.fragment_enrich_service_interface import (
    FragmentEnrichServiceInterface,
)
from app.application.services.processing.structured_processing_service import StructuredProcessingService
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.processing.fragment_enrich.enrich_fragment_request import EnrichFragmentRequest
from app.domain.dtos.processing.fragment_enrich.enrich_fragment_response import EnrichFragmentResponse
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface


class FragmentEnrichService(
    StructuredProcessingService[EnrichFragmentRequest, EnrichFragmentResponse, EnrichFragmentResponse],
    FragmentEnrichServiceInterface,
):
    label = "fragment enrichment"
    exception_cls = FragmentEnrichServiceException
    parsed_model = EnrichFragmentResponse
    llm_error_message = "El modelo de lenguaje no pudo enriquecer el fragmento."
    unexpected_error_message = "Error inesperado al enriquecer el fragmento."

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            fragment_enrich_service_settings: Optional[FragmentEnrichServiceSettings] = None,
    ) -> None:
        super().__init__(ollama_llm_facade, ollama_llm_invoker)
        self._settings = fragment_enrich_service_settings or FragmentEnrichServiceSettings()

    def _build_messages(
            self,
            request: EnrichFragmentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> list[BaseMessage]:
        content = self._truncate(request.content, self._settings.max_content_chars, authenticated_user.id, "fragment content")
        return [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=HUMAN_PROMPT.format(content=content)),
        ]

    def _request_log_extra(self, request: EnrichFragmentRequest, authenticated_user: AuthenticatedUser) -> dict:
        return {"user_id": authenticated_user.id, "content_len": len(request.content)}

    async def enrich_fragment(
            self,
            enrich_fragment_request: EnrichFragmentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> EnrichFragmentResponse:
        return await self._generate(enrich_fragment_request, authenticated_user)
