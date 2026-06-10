import json
import logging
from collections.abc import AsyncIterator
from fastapi import HTTPException, Request, status

from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import RequestValidationException
from app.application.utils.llm_json_parser import parse_json_object
from app.application.services.user_interactions.decision_brief_service.decision_brief_prompt import (
    EXTRACTION_HUMAN_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    HUMAN_PROMPT,
    RAG_QUERIES,
    build_system_prompt,
)
from app.application.services.user_interactions.decision_brief_service.decision_brief_service_exceptions import (
    DecisionBriefServiceException,
)
from app.application.services.user_interactions.decision_brief_service.decision_brief_service_interface import (
    DecisionBriefServiceInterface,
)
from app.application.services.user_interactions.decision_brief_service.decision_brief_settings import (
    DecisionBriefSettings,
)
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
from app.domain.dtos.user_interactions.decision_brief.decision_brief_request import (
    DecisionBriefGenerateRequest,
    DecisionBriefMode,
)
from app.domain.dtos.user_interactions.decision_brief.decision_brief_response import (
    DecisionBriefGenerateResponse,
    DecisionBriefOption,
)
from app.domain.dtos.user_interactions.decision_brief.decision_brief_stream_events import (
    DecisionBriefStreamComplete,
    DecisionBriefStreamError,
    DecisionBriefStreamEvent,
    DecisionBriefStreamProgress,
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
    DecisionBriefServiceException,
    UnauthorizedException,
)


def _clean(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _parse_options(raw_options: list, settings: DecisionBriefSettings) -> list[DecisionBriefOption]:
    options: list[DecisionBriefOption] = []
    for entry in raw_options[:settings.max_options]:
        if not isinstance(entry, dict):
            continue
        title = _clean(entry.get("title"), settings.max_option_title_chars)
        if not title:
            continue
        options.append(
            DecisionBriefOption(
                title=title,
                description=_clean(entry.get("description"), settings.max_option_text_chars),
                pros=_clean(entry.get("pros"), settings.max_option_text_chars),
                cons=_clean(entry.get("cons"), settings.max_option_text_chars),
                is_recommended=bool(entry.get("is_recommended", False)),
            )
        )
    return options


def _fallback_options(raw: str, settings: DecisionBriefSettings) -> tuple[
    str, str, str, str, str, list[DecisionBriefOption]]:
    lines = [ln.strip().lstrip("•-*0123456789.) ") for ln in raw.splitlines() if ln.strip()]
    options = [
        DecisionBriefOption(title=ln[:settings.max_option_title_chars])
        for ln in lines[:settings.max_options]
        if ln
    ]
    return "Brief de decisión", "", "", "", "", options


def _parse_llm_output(raw: str, settings: DecisionBriefSettings) -> tuple[
    str, str, str, str, str, list[DecisionBriefOption]]:
    try:
        data = parse_json_object(raw)
        title = _clean(data.get("title"), settings.max_title_chars) or "Brief de decisión"
        problem = _clean(data.get("problem"), settings.max_narrative_chars)
        context = _clean(data.get("context"), settings.max_narrative_chars)
        risks = _clean(data.get("risks"), settings.max_narrative_chars)
        recommendation = _clean(data.get("recommendation"), settings.max_narrative_chars)
        options = _parse_options(data.get("options", []), settings)
        if not options:
            raise ValueError("No se encontraron opciones válidas en la respuesta.")
        return title, problem, context, risks, recommendation, options
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("LLM did not return valid JSON; falling back to line-by-line parsing: %s", e)
        return _fallback_options(raw, settings)


class DecisionBriefService(DecisionBriefServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            generation_settings: GenerationSettings | None = None,
            decision_brief_settings: DecisionBriefSettings | None = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._generation_settings = generation_settings or GenerationSettings()
        self._decision_brief_settings = decision_brief_settings or DecisionBriefSettings()
        self._reformulation_processor = QueryReformulationProcessor(
            self._generation_settings, ollama_llm_facade, ollama_llm_invoker
        )
        self._context_processor = ContextRetrievalProcessor(self._generation_settings, document_context_provider)
        self._attached_processor = AttachedDocumentsProcessor(self._generation_settings, document_context_provider)
        self._reduction_processor = ContextReductionProcessor(
            self._generation_settings, ollama_llm_facade, ollama_llm_invoker
        )
        logger.info("DecisionBriefService initialized")

    def _build_state(
            self,
            request: DecisionBriefGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> GenerationState:
        return GenerationState.create(
            messages=request.messages,
            chat_id=request.chat_id,
            is_rag=request.mode == DecisionBriefMode.RAG,
            authenticated_user=authenticated_user,
            document_ids=request.document_ids,
        )

    async def _gather_context(self, state: GenerationState) -> None:
        await self._attached_processor.run(state)
        if state.is_rag:
            await self._reformulation_processor.run(state)
            await self._context_processor.run(state, RAG_QUERIES)
        await self._reduction_processor.run(state, EXTRACTION_SYSTEM_PROMPT, EXTRACTION_HUMAN_PROMPT)

    async def _invoke(self, state: GenerationState, request: DecisionBriefGenerateRequest) -> str:
        context_block = build_context_block(
            state, self._generation_settings.max_context_chars, self._generation_settings.attached_reserve_ratio
        )
        llm_messages = build_generation_messages(
            augment_system_prompt(build_system_prompt(self._decision_brief_settings), request.system_prompt, request.response_style),
            HUMAN_PROMPT,
            state,
            self._generation_settings.history_messages_window,
            context_block,
        )
        llm = await self._ollama_llm_facade.get_llm_json()
        raw = (await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_messages)).strip()
        if not raw:
            raise DecisionBriefServiceException(
                "El modelo de lenguaje devolvió una respuesta vacía.", status_code=502
            )
        return raw

    @staticmethod
    def _build_response(
            state: GenerationState,
            title: str,
            problem: str,
            context: str,
            risks: str,
            recommendation: str,
            options: list[DecisionBriefOption],
            raw: str,
    ) -> DecisionBriefGenerateResponse:
        assistant_msg = Message(role=MessageRole.assistant, content=raw)
        return DecisionBriefGenerateResponse(
            title=title,
            problem=problem,
            context=context,
            risks=risks,
            recommendation=recommendation,
            options=options,
            messages=[*state.messages, assistant_msg],
            fragments=state.all_fragments,
        )

    async def generate(
            self,
            request: DecisionBriefGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DecisionBriefGenerateResponse:
        logger.info(
            "Decision-brief generation initiated",
            extra={"user_id": authenticated_user.id, "mode": request.mode},
        )
        try:
            state = self._build_state(request, authenticated_user)
            await self._gather_context(state)

            raw = await self._invoke(state, request)
            title, problem, context, risks, recommendation, options = _parse_llm_output(raw,
                                                                                        self._decision_brief_settings)
            if not options:
                raise DecisionBriefServiceException(
                    "No se pudieron extraer opciones de la respuesta del modelo.", status_code=502
                )

            logger.info(
                "Decision-brief generation completed",
                extra={
                    "user_id": authenticated_user.id,
                    "options_count": len(options),
                    "fragments_used": len(state.all_fragments),
                },
            )
            return self._build_response(
                state, title, problem, context, risks, recommendation, options, raw
            )

        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during decision-brief generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise DecisionBriefServiceException(
                "Error inesperado durante la generación del brief de decisión.", status_code=500
            ) from e

    async def generate_stream(
            self,
            request: DecisionBriefGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[DecisionBriefStreamEvent]:
        try:
            state = self._build_state(request, authenticated_user)
            if state.document_ids:
                yield DecisionBriefStreamProgress(
                    step="loading_documents",
                    message="Leyendo documentos adjuntos...",
                )
                await self._attached_processor.run(state)
                if state.is_rag:
                    yield DecisionBriefStreamProgress(
                        step="searching",
                        message="Buscando contexto adicional en la base de conocimiento...",
                    )
                    await self._reformulation_processor.run(state)
                    await self._context_processor.run(state, RAG_QUERIES)
            elif state.is_rag:
                yield DecisionBriefStreamProgress(
                    step="searching",
                    message="Buscando información relevante en los documentos...",
                )
                await self._reformulation_processor.run(state)
                await self._context_processor.run(state, RAG_QUERIES)
            await self._reduction_processor.run(state, EXTRACTION_SYSTEM_PROMPT, EXTRACTION_HUMAN_PROMPT)

            yield DecisionBriefStreamProgress(step="generation", message="Analizando opciones y elaborando el brief de decisión...")

            raw = await self._invoke(state, request)
            title, problem, context, risks, recommendation, options = _parse_llm_output(raw,
                                                                                        self._decision_brief_settings)
            if not options:
                raise DecisionBriefServiceException(
                    "No se pudieron extraer opciones de la respuesta del modelo.", status_code=502
                )

            yield DecisionBriefStreamComplete(
                result=self._build_response(
                    state, title, problem, context, risks, recommendation, options, raw
                )
            )
        except _KNOWN_EXCEPTIONS as e:
            logger.warning(
                "Known error during decision-brief stream generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            yield DecisionBriefStreamError(message=str(e), code=type(e).__name__)
        except Exception as e:
            logger.exception(
                "Unexpected error during decision-brief stream generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            yield DecisionBriefStreamError(
                message="Error inesperado durante la generación del brief de decisión.",
                code="internal_error",
            )


async def get_decision_brief_service(request: Request) -> DecisionBriefServiceInterface:
    try:
        return request.app.state.decision_brief_service
    except AttributeError:
        logger.error("DecisionBriefService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Decision-brief service is not available",
        )
