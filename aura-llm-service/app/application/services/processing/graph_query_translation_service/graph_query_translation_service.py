from typing import Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.application.services.processing.graph_query_translation_service.exceptions.graph_query_translation_service_exceptions import (
    GraphQueryTranslationServiceException,
)
from app.application.services.processing.graph_query_translation_service.graph_query_translation_prompt import (
    HUMAN_PROMPT,
    REPAIR_PROMPT,
    SYSTEM_PROMPT,
)
from app.application.services.processing.graph_query_translation_service.graph_query_translation_settings import (
    GraphQueryTranslationServiceSettings,
)
from app.application.services.processing.graph_query_translation_service.interfaces.graph_query_translation_service_interface import (
    GraphQueryTranslationServiceInterface,
)
from app.application.services.processing.structured_processing_service import StructuredProcessingService
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.processing.graph_query_translation.translate_graph_query_request import (
    TranslateGraphQueryRequest,
)
from app.domain.dtos.processing.graph_query_translation.translate_graph_query_response import (
    TranslateGraphQueryResponse,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface


class GraphQueryTranslationService(
    StructuredProcessingService[
        TranslateGraphQueryRequest, TranslateGraphQueryResponse, TranslateGraphQueryResponse
    ],
    GraphQueryTranslationServiceInterface,
):
    label = "graph query translation"
    exception_cls = GraphQueryTranslationServiceException
    parsed_model = TranslateGraphQueryResponse
    llm_error_message = "El modelo de lenguaje no pudo traducir la pregunta a una intención de grafo."
    unexpected_error_message = "Error inesperado al traducir la pregunta a una intención de grafo."

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            graph_query_translation_service_settings: Optional[GraphQueryTranslationServiceSettings] = None,
    ) -> None:
        super().__init__(ollama_llm_facade, ollama_llm_invoker)
        self._settings = graph_query_translation_service_settings or GraphQueryTranslationServiceSettings()

    def _build_messages(
            self,
            request: TranslateGraphQueryRequest,
            authenticated_user: AuthenticatedUser,
    ) -> list[BaseMessage]:
        question = self._truncate(
            request.question, self._settings.max_question_chars, authenticated_user.id, "question"
        )
        relation_types = request.ontology.relation_types
        relation_types_text = ", ".join(relation_types) if relation_types else "(sin restricción)"
        return [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=HUMAN_PROMPT.format(
                    entity_types=", ".join(request.ontology.entity_types),
                    relation_types=relation_types_text,
                    question=question,
                )
            ),
        ]

    def _max_repair_attempts(self, request: TranslateGraphQueryRequest) -> int:
        return self._settings.max_repair_attempts

    def _build_repair_messages(
            self,
            original_messages: list[BaseMessage],
            malformed_output: str,
            parse_error: str,
    ) -> list[BaseMessage]:
        repair = HumanMessage(
            content=REPAIR_PROMPT.format(
                parse_error=parse_error[:500],
                malformed_output=malformed_output[:2_000],
            )
        )
        return [*original_messages, repair]

    def _request_log_extra(self, request: TranslateGraphQueryRequest, authenticated_user: AuthenticatedUser) -> dict:
        return {
            "user_id": authenticated_user.id,
            "question_len": len(request.question),
            "entity_types_count": len(request.ontology.entity_types),
            "relation_types_count": len(request.ontology.relation_types),
        }

    def _result_log_extra(self, result: TranslateGraphQueryResponse) -> dict:
        return {"intent": result.intent.value, "confidence": result.confidence}

    async def translate_graph_query(
            self,
            translate_graph_query_request: TranslateGraphQueryRequest,
            authenticated_user: AuthenticatedUser,
    ) -> TranslateGraphQueryResponse:
        return await self._generate(translate_graph_query_request, authenticated_user)
