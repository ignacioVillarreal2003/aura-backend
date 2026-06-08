import json
import logging
from typing import Optional
from fastapi import HTTPException, Request, status
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import RequestValidationException
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
from app.application.services.processing.graph_query_translation_service.graph_query_translation_state import (
    GraphQueryTranslationState,
)
from app.application.services.processing.graph_query_translation_service.interfaces.graph_query_translation_service_interface import (
    GraphQueryTranslationServiceInterface,
)
from app.application.utils.llm_json_parser import parse_json_object
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.processing.graph_query_translation.translate_graph_query_request import (
    TranslateGraphQueryRequest,
)
from app.domain.dtos.processing.graph_query_translation.translate_graph_query_response import (
    TranslateGraphQueryResponse,
)
from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    GraphQueryTranslationServiceException,
    UnauthorizedException,
)


class GraphQueryTranslationService(GraphQueryTranslationServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            graph_query_translation_service_settings: Optional[GraphQueryTranslationServiceSettings] = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._graph_query_translation_settings = (
            graph_query_translation_service_settings or GraphQueryTranslationServiceSettings()
        )

    async def translate_graph_query(
            self,
            translate_graph_query_request: TranslateGraphQueryRequest,
            authenticated_user: AuthenticatedUser,
    ) -> TranslateGraphQueryResponse:
        log_extra = {
            "user_id": authenticated_user.id,
            "question_len": len(translate_graph_query_request.question),
            "entity_types_count": len(translate_graph_query_request.ontology.entity_types),
            "relation_types_count": len(translate_graph_query_request.ontology.relation_types),
        }
        logger.info("Graph query translation initiated", extra=log_extra)
        try:
            state = self._build_state(translate_graph_query_request, authenticated_user)
            result = await self._run(state)
            logger.info(
                "Graph query translation completed",
                extra={
                    **log_extra,
                    "intent": result.intent.value,
                    "confidence": result.confidence,
                },
            )
            return result
        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during graph query translation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise GraphQueryTranslationServiceException(
                "Error inesperado al traducir la pregunta a una intención de grafo."
            ) from e

    def _build_state(
            self,
            request: TranslateGraphQueryRequest,
            authenticated_user: AuthenticatedUser,
    ) -> GraphQueryTranslationState:
        question = self._truncate_question(request.question, authenticated_user.id)
        return GraphQueryTranslationState(
            authenticated_user=authenticated_user,
            question=question,
            entity_types=tuple(request.ontology.entity_types),
            relation_types=tuple(request.ontology.relation_types),
        )

    async def _run(self, state: GraphQueryTranslationState) -> TranslateGraphQueryResponse:
        raw, original_llm_input = await self._invoke_llm(state)
        last_error: Exception | None = None

        for attempt in range(self._graph_query_translation_settings.max_repair_attempts + 1):
            try:
                result = self._parse_response(raw, state.authenticated_user.id)
                if attempt > 0:
                    logger.info(
                        "Graph query translation JSON repair succeeded",
                        extra={"user_id": state.authenticated_user.id, "attempt": attempt},
                    )
                return result
            except GraphQueryTranslationServiceException as exc:
                last_error = exc
                if attempt >= self._graph_query_translation_settings.max_repair_attempts:
                    break
                logger.warning(
                    "Graph query translation JSON malformed; attempting repair",
                    extra={
                        "user_id": state.authenticated_user.id,
                        "attempt": attempt + 1,
                        "max_repair_attempts": self._graph_query_translation_settings.max_repair_attempts,
                    },
                )
                raw = await self._invoke_repair(
                    original_llm_input=original_llm_input,
                    malformed_output=raw,
                    parse_error=str(exc),
                    user_id=state.authenticated_user.id,
                )

        raise last_error  # type: ignore[misc]

    def _truncate_question(self, question: str, user_id: int) -> str:
        if len(question) <= self._graph_query_translation_settings.max_question_chars:
            return question
        logger.info(
            "Truncating question for graph query translation",
            extra={
                "original_len": len(question),
                "max_chars": self._graph_query_translation_settings.max_question_chars,
                "user_id": user_id,
            },
        )
        return question[: self._graph_query_translation_settings.max_question_chars]

    def _build_llm_input(self, state: GraphQueryTranslationState) -> list:
        relation_types_text = (
            ", ".join(state.relation_types)
            if state.relation_types
            else "(sin restricción)"
        )
        return [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=HUMAN_PROMPT.format(
                    entity_types=", ".join(state.entity_types),
                    relation_types=relation_types_text,
                    question=state.question,
                )
            ),
        ]

    async def _invoke_llm(self, state: GraphQueryTranslationState) -> tuple[str, list]:
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
                "LLM invocation failed during graph query translation",
                extra={"user_id": user_id, "error_type": type(e).__name__},
            )
            raise GraphQueryTranslationServiceException(
                "El modelo de lenguaje no pudo traducir la pregunta a una intención de grafo.",
                status_code=502,
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected LLM error during graph query translation",
                extra={"user_id": user_id, "error_type": type(e).__name__},
            )
            raise GraphQueryTranslationServiceException(
                "El modelo de lenguaje no pudo traducir la pregunta a una intención de grafo.",
                status_code=502,
            ) from e

    def _parse_response(self, raw: str, user_id: int) -> TranslateGraphQueryResponse:
        try:
            data = parse_json_object(raw)
            return TranslateGraphQueryResponse.model_validate(data)
        except (ValidationError, json.JSONDecodeError, TypeError) as e:
            logger.warning(
                "Failed to parse graph query translation JSON from LLM",
                extra={"user_id": user_id, "error_type": type(e).__name__, "error": str(e)},
            )
            raise GraphQueryTranslationServiceException(
                "La respuesta del modelo no tiene el formato JSON esperado.",
                status_code=502,
            ) from e


async def get_graph_query_translation_service(request: Request) -> GraphQueryTranslationServiceInterface:
    try:
        return request.app.state.graph_query_translation_service
    except AttributeError:
        logger.error("GraphQueryTranslationService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GraphQueryTranslationService is not available",
        )
