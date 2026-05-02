import json
import logging
from typing import Optional

from fastapi import HTTPException, Request, status
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.authorization.permissions import Permissions
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.graph_extraction_service.exceptions.graph_extraction_service_exceptions import (
    GraphExtractionServiceException,
)
from app.application.services.graph_extraction_service.graph_extraction_prompt import (
    HUMAN_PROMPT,
    SYSTEM_PROMPT,
)
from app.application.services.graph_extraction_service.graph_extraction_settings import (
    GraphExtractionServiceSettings,
)
from app.application.services.graph_extraction_service.graph_extraction_state import (
    GraphExtractionState,
)
from app.application.services.graph_extraction_service.interfaces.graph_extraction_service_interface import (
    GraphExtractionServiceInterface,
)
from app.application.utils.llm_json_parser import parse_json_object
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.extraction.extract_entities_relations_request import (
    ExtractEntitiesRelationsRequest,
)
from app.domain.dtos.graph.extraction.extract_entities_relations_response import (
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
            authorizer: Authorizer,
            graph_extraction_service_settings: Optional[GraphExtractionServiceSettings] = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._authorizer = authorizer
        self._settings = graph_extraction_service_settings or GraphExtractionServiceSettings()

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
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_GRAPH_EXTRACTION}),
        )
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
            allowed_entity_types=list(request.allowed_entity_types),
            allowed_relation_types=(
                list(request.allowed_relation_types)
                if request.allowed_relation_types is not None
                else None
            ),
            max_entities=request.max_entities,
            max_relations=request.max_relations,
        )

    async def _run(self, state: GraphExtractionState) -> ExtractEntitiesRelationsResponse:
        raw = await self._invoke_llm(state)
        return self._parse_response(raw, state.authenticated_user.id)

    def _truncate_content(self, content: str, user_id: int) -> str:
        if len(content) <= self._settings.max_content_chars:
            return content
        logger.info(
            "Truncating fragment content for graph extraction",
            extra={
                "original_len": len(content),
                "max_chars": self._settings.max_content_chars,
                "user_id": user_id,
            },
        )
        return content[: self._settings.max_content_chars]

    async def _invoke_llm(self, state: GraphExtractionState) -> str:
        user_id = state.authenticated_user.id
        allowed_relation_types_text = (
            ", ".join(state.allowed_relation_types)
            if state.allowed_relation_types
            else "(sin restricción; usar snake_case y mantener tipos coherentes)"
        )
        llm_input = [
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
        try:
            llm = await self._ollama_llm_facade.get_llm_base()
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


async def get_graph_extraction_service(request: Request) -> GraphExtractionServiceInterface:
    try:
        return request.app.state.graph_extraction_service
    except AttributeError:
        logger.error("GraphExtractionService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GraphExtractionService is not available",
        )
