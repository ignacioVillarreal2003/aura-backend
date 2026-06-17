from typing import Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.application.services.processing.graph_extraction_service.exceptions.graph_extraction_service_exceptions import (
    GraphExtractionServiceException,
)
from app.application.services.processing.graph_extraction_service.graph_extraction_prompt import (
    HUMAN_PROMPT,
    REPAIR_PROMPT,
    SYSTEM_PROMPT,
)
from app.application.services.processing.graph_extraction_service.graph_extraction_settings import (
    GraphExtractionServiceSettings,
)
from app.application.services.processing.graph_extraction_service.interfaces.graph_extraction_service_interface import (
    GraphExtractionServiceInterface,
)
from app.application.services.processing.structured_processing_service import StructuredProcessingService
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.processing.graph_extraction.extract_entities_relations_request import (
    ExtractEntitiesRelationsRequest,
)
from app.domain.dtos.processing.graph_extraction.extract_entities_relations_response import (
    ExtractEntitiesRelationsResponse,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface


class GraphExtractionService(
    StructuredProcessingService[
        ExtractEntitiesRelationsRequest, ExtractEntitiesRelationsResponse, ExtractEntitiesRelationsResponse
    ],
    GraphExtractionServiceInterface,
):
    label = "graph extraction"
    exception_cls = GraphExtractionServiceException
    parsed_model = ExtractEntitiesRelationsResponse
    llm_error_message = "El modelo de lenguaje no pudo extraer entidades y relaciones."
    unexpected_error_message = "Error inesperado al extraer entidades y relaciones."

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            graph_extraction_service_settings: Optional[GraphExtractionServiceSettings] = None,
    ) -> None:
        super().__init__(ollama_llm_facade, ollama_llm_invoker)
        self._settings = graph_extraction_service_settings or GraphExtractionServiceSettings()

    def _build_messages(
            self,
            request: ExtractEntitiesRelationsRequest,
            authenticated_user: AuthenticatedUser,
    ) -> list[BaseMessage]:
        content = self._truncate(
            request.content, self._settings.max_content_chars, authenticated_user.id, "fragment content"
        )
        allowed_relation_types_text = (
            ", ".join(request.allowed_relation_types)
            if request.allowed_relation_types
            else "(sin restricción; usar snake_case y mantener tipos coherentes)"
        )
        return [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=HUMAN_PROMPT.format(
                    document_id=request.document_id,
                    fragment_id=request.fragment_id,
                    allowed_entity_types=", ".join(request.allowed_entity_types),
                    allowed_relation_types=allowed_relation_types_text,
                    max_entities=request.max_entities,
                    max_relations=request.max_relations,
                    content=content,
                )
            ),
        ]

    def _max_repair_attempts(self, request: ExtractEntitiesRelationsRequest) -> int:
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

    def _request_log_extra(self, request: ExtractEntitiesRelationsRequest, authenticated_user: AuthenticatedUser) -> dict:
        return {
            "user_id": authenticated_user.id,
            "document_id": request.document_id,
            "fragment_id": request.fragment_id,
            "content_len": len(request.content),
            "allowed_entity_types_count": len(request.allowed_entity_types),
            "allowed_relation_types_count": (
                len(request.allowed_relation_types)
                if request.allowed_relation_types is not None
                else None
            ),
        }

    def _result_log_extra(self, result: ExtractEntitiesRelationsResponse) -> dict:
        return {"entities_count": len(result.entities), "relations_count": len(result.relations)}

    def _postprocess(
            self,
            parsed: ExtractEntitiesRelationsResponse,
            request: ExtractEntitiesRelationsRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ExtractEntitiesRelationsResponse:
        raw_allowed = {t.lower() for t in request.allowed_entity_types}
        allowed_entity_set = {EntityType.parse(t).value for t in request.allowed_entity_types}
        unmapped = raw_allowed - allowed_entity_set
        if unmapped:
            self._logger.warning(
                "Some allowed_entity_types are not in the EntityType vocabulary and were mapped to 'other'",
                extra={"unmapped_types": sorted(unmapped), "user_id": authenticated_user.id},
            )

        allowed_relation_set = (
            {t.lower() for t in request.allowed_relation_types}
            if request.allowed_relation_types
            else None
        )
        min_conf = self._settings.min_relation_confidence

        filtered_entities: list = []
        seen_entities: set[tuple[str, str]] = set()
        for e in parsed.entities:
            if e.type.value not in allowed_entity_set:
                continue
            key = (e.name.strip().lower(), e.type.value)
            if key in seen_entities:
                continue
            seen_entities.add(key)
            filtered_entities.append(e)

        filtered_relations: list = []
        seen_relations: set[tuple[str, str, str, str, str]] = set()
        for r in parsed.relations:
            if allowed_relation_set is not None and r.type.lower() not in allowed_relation_set:
                continue
            if r.confidence < min_conf:
                continue
            if (
                    r.source.type.value not in allowed_entity_set
                    or r.target.type.value not in allowed_entity_set
            ):
                continue
            key = (
                r.source.name.strip().lower(),
                r.source.type.value,
                r.target.name.strip().lower(),
                r.target.type.value,
                r.type.lower(),
            )
            if key in seen_relations:
                continue
            seen_relations.add(key)
            filtered_relations.append(r)

        discarded_entities = len(parsed.entities) - len(filtered_entities)
        discarded_relations = len(parsed.relations) - len(filtered_relations)
        if discarded_entities or discarded_relations:
            self._logger.debug(
                "Post-parse filters removed out-of-whitelist or low-confidence items",
                extra={
                    "discarded_entities": discarded_entities,
                    "discarded_relations": discarded_relations,
                    "min_confidence": min_conf,
                },
            )

        return ExtractEntitiesRelationsResponse(entities=filtered_entities, relations=filtered_relations)

    async def extract_entities_relations(
            self,
            extract_entities_relations_request: ExtractEntitiesRelationsRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ExtractEntitiesRelationsResponse:
        return await self._generate(extract_entities_relations_request, authenticated_user)
