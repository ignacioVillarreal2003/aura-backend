import json
import logging
from collections.abc import AsyncIterator
from fastapi import HTTPException, Request, status

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import RequestValidationException
from app.application.utils.llm_json_parser import parse_json_object
from app.application.services.user_interactions.timeline_service.timeline_prompt import (
    EXTRACTION_HUMAN_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    HUMAN_PROMPT,
    RAG_QUERIES,
    build_system_prompt,
)
from app.application.services.user_interactions.timeline_service.timeline_service_exceptions import (
    TimelineServiceException,
)
from app.application.services.user_interactions.timeline_service.timeline_service_interface import (
    TimelineServiceInterface,
)
from app.application.services.user_interactions.timeline_service.timeline_settings import TimelineSettings
from app.application.services.generation_shared.generation_messages import (
    build_context_block,
    build_generation_messages,
)
from app.application.services.generation_shared.prompt_augmentation import augment_system_prompt
from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.generation_shared.generation_state import GenerationState
from app.application.services.generation_shared.processors.attached_documents_processor import (
    AttachedDocumentsProcessor,
)
from app.application.services.generation_shared.processors.context_reduction_processor import (
    ContextReductionProcessor,
)
from app.application.services.generation_shared.processors.context_retrieval_processor import (
    ContextRetrievalProcessor,
)
from app.application.services.generation_shared.processors.query_reformulation_processor import (
    QueryReformulationProcessor,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.user_interactions.timeline.timeline_request import TimelineGenerateRequest, TimelineMode
from app.domain.dtos.user_interactions.timeline.timeline_response import TimelineEvent, TimelineGenerateResponse
from app.domain.dtos.user_interactions.timeline.timeline_stream_events import (
    TimelineStreamComplete,
    TimelineStreamError,
    TimelineStreamEvent,
    TimelineStreamProgress,
)
from app.domain.dtos.message import Message
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    TimelineServiceException,
    UnauthorizedException,
)


def _clean(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _parse_events(raw_events: list, settings: TimelineSettings) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for entry in raw_events[:settings.max_events]:
        if not isinstance(entry, dict):
            continue
        event_title = _clean(entry.get("event"), settings.max_event_chars)
        if not event_title:
            continue
        events.append(
            TimelineEvent(
                event=event_title,
                description=_clean(entry.get("description"), settings.max_description_chars),
                occurred_label=_clean(entry.get("occurred_label"), settings.max_label_chars),
            )
        )
    return events


def _fallback_events(raw: str, settings: TimelineSettings) -> tuple[str, str, list[TimelineEvent]]:
    lines = [ln.strip().lstrip("•-*0123456789.) ") for ln in raw.splitlines() if ln.strip()]
    events = [
        TimelineEvent(event=ln[:settings.max_event_chars], description="", occurred_label="")
        for ln in lines[:settings.max_events]
        if ln
    ]
    return "Línea de tiempo", "", events


def _parse_llm_output(raw: str, settings: TimelineSettings) -> tuple[str, str, list[TimelineEvent]]:
    try:
        data = parse_json_object(raw)
        title = _clean(data.get("title"), settings.max_title_chars) or "Línea de tiempo"
        summary = _clean(data.get("summary"), settings.max_summary_chars)
        events = _parse_events(data.get("events", []), settings)
        if not events:
            raise ValueError("No se encontraron eventos válidos en la respuesta.")
        return title, summary, events
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("LLM did not return valid JSON; falling back to line-by-line parsing: %s", e)
        return _fallback_events(raw, settings)


class TimelineService(TimelineServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            generation_settings: GenerationSettings | None = None,
            timeline_settings: TimelineSettings | None = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._generation_settings = generation_settings or GenerationSettings()
        self._timeline_settings = timeline_settings or TimelineSettings()
        self._reformulation_processor = QueryReformulationProcessor(
            self._generation_settings, ollama_llm_facade, ollama_llm_invoker
        )
        self._context_processor = ContextRetrievalProcessor(self._generation_settings, document_context_provider)
        self._attached_processor = AttachedDocumentsProcessor(self._generation_settings, document_context_provider)
        self._reduction_processor = ContextReductionProcessor(
            self._generation_settings, ollama_llm_facade, ollama_llm_invoker
        )
        logger.info("TimelineService initialized")

    def _build_state(
            self,
            request: TimelineGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> GenerationState:
        return GenerationState.create(
            messages=request.messages,
            chat_id=request.chat_id,
            is_rag=request.mode == TimelineMode.RAG,
            authenticated_user=authenticated_user,
            document_ids=request.document_ids,
        )

    async def _gather_context(self, state: GenerationState) -> None:
        await self._attached_processor.run(state)
        if state.is_rag:
            await self._reformulation_processor.run(state)
            await self._context_processor.run(state, RAG_QUERIES)
        await self._reduction_processor.run(state, EXTRACTION_SYSTEM_PROMPT, EXTRACTION_HUMAN_PROMPT)

    async def _invoke(self, state: GenerationState, request: TimelineGenerateRequest) -> str:
        context_block = build_context_block(
            state, self._generation_settings.max_context_chars, self._generation_settings.attached_reserve_ratio
        )
        llm_messages = build_generation_messages(
            augment_system_prompt(build_system_prompt(self._timeline_settings), request.system_prompt, request.response_style),
            HUMAN_PROMPT,
            state,
            self._generation_settings.history_messages_window,
            context_block,
        )
        llm = await self._ollama_llm_facade.get_llm_json()
        raw = (await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_messages)).strip()
        if not raw:
            raise TimelineServiceException(
                "El modelo de lenguaje devolvió una respuesta vacía.", status_code=502
            )
        return raw

    @staticmethod
    def _build_response(
            state: GenerationState,
            title: str,
            summary: str,
            events: list[TimelineEvent],
            raw: str,
    ) -> TimelineGenerateResponse:
        assistant_msg = Message(role=MessageRole.assistant, content=raw)
        return TimelineGenerateResponse(
            title=title,
            summary=summary,
            events=events,
            messages=[*state.messages, assistant_msg],
            fragments=state.all_fragments,
        )

    async def generate(
            self,
            request: TimelineGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> TimelineGenerateResponse:
        logger.info(
            "Timeline generation initiated",
            extra={"user_id": authenticated_user.id, "mode": request.mode},
        )

        try:
            state = self._build_state(request, authenticated_user)
            await self._gather_context(state)

            raw = await self._invoke(state, request)
            title, summary, events = _parse_llm_output(raw, self._timeline_settings)
            if not events:
                raise TimelineServiceException(
                    "No se pudieron extraer eventos de la respuesta del modelo.", status_code=502
                )

            logger.info(
                "Timeline generation completed",
                extra={
                    "user_id": authenticated_user.id,
                    "events_count": len(events),
                    "fragments_used": len(state.all_fragments),
                },
            )
            return self._build_response(state, title, summary, events, raw)

        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during timeline generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise TimelineServiceException(
                "Error inesperado durante la generación de la línea de tiempo.", status_code=500
            ) from e

    async def generate_stream(
            self,
            request: TimelineGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[TimelineStreamEvent]:
        try:
            state = self._build_state(request, authenticated_user)
            if state.document_ids:
                yield TimelineStreamProgress(
                    step="loading_documents",
                    message="Leyendo documentos adjuntos...",
                )
                await self._attached_processor.run(state)
                if state.is_rag:
                    yield TimelineStreamProgress(
                        step="searching",
                        message="Buscando contexto adicional en la base de conocimiento...",
                    )
                    await self._reformulation_processor.run(state)
                    await self._context_processor.run(state, RAG_QUERIES)
            elif state.is_rag:
                yield TimelineStreamProgress(
                    step="searching",
                    message="Buscando información relevante en los documentos...",
                )
                await self._reformulation_processor.run(state)
                await self._context_processor.run(state, RAG_QUERIES)
            await self._reduction_processor.run(state, EXTRACTION_SYSTEM_PROMPT, EXTRACTION_HUMAN_PROMPT)

            yield TimelineStreamProgress(step="generation", message="Identificando y ordenando eventos cronológicamente...")

            raw = await self._invoke(state, request)
            title, summary, events = _parse_llm_output(raw, self._timeline_settings)
            if not events:
                raise TimelineServiceException(
                    "No se pudieron extraer eventos de la respuesta del modelo.", status_code=502
                )

            yield TimelineStreamComplete(result=self._build_response(state, title, summary, events, raw))
        except _KNOWN_EXCEPTIONS as e:
            logger.warning(
                "Known error during timeline stream generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            yield TimelineStreamError(message=str(e), code=type(e).__name__)
        except Exception as e:
            logger.exception(
                "Unexpected error during timeline stream generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            yield TimelineStreamError(
                message="Error inesperado durante la generación de la línea de tiempo.",
                code="internal_error",
            )


async def get_timeline_service(request: Request) -> TimelineServiceInterface:
    try:
        return request.app.state.timeline_service
    except AttributeError:
        logger.error("TimelineService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Timeline service is not available",
        )
