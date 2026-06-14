import json
import logging
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from app.application.authorization.exceptions.authorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import RequestValidationException
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
from app.application.services.processing.graph_extraction_service.graph_extraction_state import (
    GraphExtractionState,
)
from app.application.services.processing.graph_extraction_service.interfaces.graph_extraction_service_interface import (
    GraphExtractionServiceInterface,
)
from app.application.utils.llm_json_parser import parse_json_object
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.processing.graph_extraction.extract_entities_relations_request import (
    ExtractEntitiesRelationsRequest,
)
from app.domain.dtos.processing.graph_extraction.extract_entities_relations_response import (
    ExtractEntitiesRelationsResponse,
)
from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    GraphExtractionServiceException,
    UnauthorizedException,
)


class GraphExtractionService(GraphExtractionServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            graph_extraction_service_settings: Optional[GraphExtractionServiceSettings] = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._graph_extraction_settings = graph_extraction_service_settings or GraphExtractionServiceSettings()

    async def extract_entities_relations(
            self,
            extract_entities_relations_request: ExtractEntitiesRelationsRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ExtractEntitiesRelationsResponse:
        log_extra = {
            "user_id": authenticated_user.id,
            "document_id": extract_entities_relations_request.document_id,
            "fragment_id": extract_entities_relations_request.fragment_id,
            "content_len": len(extract_entities_relations_request.content),
            "allowed_entity_types_count": len(extract_entities_relations_request.allowed_entity_types),
            "allowed_relation_types_count": (
                len(extract_entities_relations_request.allowed_relation_types)
                if extract_entities_relations_request.allowed_relation_types is not None
                else None
            ),
        }
        logger.info("Graph extraction initiated", extra=log_extra)
        try:
            state = self._build_state(extract_entities_relations_request, authenticated_user)
            result = await self._run(state)
            logger.info(
                "Graph extraction completed",
                extra={
                    **log_extra,
                    "entities_count": len(result.entities),
                    "relations_count": len(result.relations),
                },
            )
            return result
        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during graph extraction",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise GraphExtractionServiceException(
                "Error inesperado al extraer entidades y relaciones."
            ) from e

    def _build_state(
            self,
            request: ExtractEntitiesRelationsRequest,
            authenticated_user: AuthenticatedUser,
    ) -> GraphExtractionState:
        content = self._truncate_content(request.content, authenticated_user.id)
        return GraphExtractionState(
            authenticated_user=authenticated_user,
            content=content,
            document_id=request.document_id,
            fragment_id=request.fragment_id,
            allowed_entity_types=tuple(request.allowed_entity_types),
            allowed_relation_types=(
                tuple(request.allowed_relation_types)
                if request.allowed_relation_types is not None
                else None
            ),
            max_entities=request.max_entities,
            max_relations=request.max_relations,
        )

    async def _run(self, state: GraphExtractionState) -> ExtractEntitiesRelationsResponse:
        raw, original_llm_input = await self._invoke_llm(state)
        last_error: Exception | None = None

        for attempt in range(self._graph_extraction_settings.max_repair_attempts + 1):
            try:
                result = self._parse_response(raw, state.authenticated_user.id)
                if attempt > 0:
                    logger.info(
                        "Graph extraction JSON repair succeeded",
                        extra={"user_id": state.authenticated_user.id, "attempt": attempt},
                    )
                return self._apply_filters(result, state)
            except GraphExtractionServiceException as exc:
                last_error = exc
                if attempt >= self._graph_extraction_settings.max_repair_attempts:
                    break
                logger.warning(
                    "Graph extraction JSON malformed; attempting repair",
                    extra={
                        "user_id": state.authenticated_user.id,
                        "attempt": attempt + 1,
                        "max_repair_attempts": self._graph_extraction_settings.max_repair_attempts,
                    },
                )
                raw = await self._invoke_repair(
                    original_llm_input=original_llm_input,
                    malformed_output=raw,
                    parse_error=str(exc),
                    user_id=state.authenticated_user.id,
                )

        raise last_error  # type: ignore[misc]

    def _truncate_content(self, content: str, user_id: int) -> str:
        if len(content) <= self._graph_extraction_settings.max_content_chars:
            return content
        logger.info(
            "Truncating fragment content for graph extraction",
            extra={
                "original_len": len(content),
                "max_chars": self._graph_extraction_settings.max_content_chars,
                "user_id": user_id,
            },
        )
        return content[: self._graph_extraction_settings.max_content_chars]

    def _build_llm_input(self, state: GraphExtractionState) -> list:
        allowed_relation_types_text = (
            ", ".join(state.allowed_relation_types)
            if state.allowed_relation_types
            else "(sin restricción; usar snake_case y mantener tipos coherentes)"
        )
        return [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=HUMAN_PROMPT.format(
                    document_id=state.document_id,
                    fragment_id=state.fragment_id,
                    allowed_entity_types=", ".join(state.allowed_entity_types),
                    allowed_relation_types=allowed_relation_types_text,
                    max_entities=state.max_entities,
                    max_relations=state.max_relations,
                    content=state.content,
                )
            ),
        ]

    async def _invoke_llm(self, state: GraphExtractionState) -> tuple[str, list]:
        llm_input = self._build_llm_input(state)
        raw = await self._call_llm_json(llm_input, state.authenticated_user.id)
        return raw, llm_input

    async def _invoke_repair(
            self,
            original_llm_input: list,
            malformed_output: str,
            parse_error: str,
            user_id: int,
    ) -> str:
        repair_message = HumanMessage(
            content=REPAIR_PROMPT.format(
                parse_error=parse_error[:500],
                malformed_output=malformed_output[:2_000],
            )
        )
        llm_input = [*original_llm_input, repair_message]
        return await self._call_llm_json(llm_input, user_id)

    async def _call_llm_json(self, llm_input: list, user_id: int) -> str:
        try:
            llm = await self._ollama_llm_facade.get_llm_json()
            return await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
        except LLMInvocationError as e:
            logger.warning(
                "LLM invocation failed during graph extraction",
                extra={"user_id": user_id, "error_type": type(e).__name__},
            )
            raise GraphExtractionServiceException(
                "El modelo de lenguaje no pudo extraer entidades y relaciones.",
                status_code=502,
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected LLM error during graph extraction",
                extra={"user_id": user_id, "error_type": type(e).__name__},
            )
            raise GraphExtractionServiceException(
                "El modelo de lenguaje no pudo extraer entidades y relaciones.",
                status_code=502,
            ) from e

    def _parse_response(self, raw: str, user_id: int) -> ExtractEntitiesRelationsResponse:
        try:
            data = parse_json_object(raw)
            return ExtractEntitiesRelationsResponse.model_validate(data)
        except (ValidationError, json.JSONDecodeError, TypeError) as e:
            logger.warning(
                "Failed to parse graph extraction JSON from LLM",
                extra={"user_id": user_id, "error_type": type(e).__name__, "error": str(e)},
            )
            raise GraphExtractionServiceException(
                "La respuesta del modelo no tiene el formato JSON esperado.",
                status_code=502,
            ) from e

    def _apply_filters(
            self,
            result: ExtractEntitiesRelationsResponse,
            state: GraphExtractionState,
    ) -> ExtractEntitiesRelationsResponse:
        raw_allowed = {t.lower() for t in state.allowed_entity_types}
        allowed_entity_set = {EntityType.parse(t).value for t in state.allowed_entity_types}
        unmapped = raw_allowed - allowed_entity_set
        if unmapped:
            logger.warning(
                "Some allowed_entity_types are not in the EntityType vocabulary and were mapped to 'other'",
                extra={
                    "unmapped_types": sorted(unmapped),
                    "user_id": state.authenticated_user.id,
                },
            )

        allowed_relation_set = (
            {t.lower() for t in state.allowed_relation_types}
            if state.allowed_relation_types
            else None
        )
        min_conf = self._graph_extraction_settings.min_relation_confidence

        filtered_entities: list = []
        seen_entities: set[tuple[str, str]] = set()
        for e in result.entities:
            if e.type.value not in allowed_entity_set:
                continue
            key = (e.name.strip().lower(), e.type.value)
            if key in seen_entities:
                continue
            seen_entities.add(key)
            filtered_entities.append(e)

        filtered_relations: list = []
        seen_relations: set[tuple[str, str, str, str, str]] = set()
        for r in result.relations:
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

        discarded_entities = len(result.entities) - len(filtered_entities)
        discarded_relations = len(result.relations) - len(filtered_relations)
        if discarded_entities or discarded_relations:
            logger.debug(
                "Post-parse filters removed out-of-whitelist or low-confidence items",
                extra={
                    "discarded_entities": discarded_entities,
                    "discarded_relations": discarded_relations,
                    "min_confidence": min_conf,
                },
            )

        return ExtractEntitiesRelationsResponse(
            entities=filtered_entities,
            relations=filtered_relations,
        )
