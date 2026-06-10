import json
import logging
from collections.abc import AsyncIterator
from fastapi import HTTPException, Request, status

from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import RequestValidationException
from app.application.utils.llm_json_parser import parse_json_object
from app.application.services.user_interactions.checklist_service.checklist_prompt import (
    EXTRACTION_HUMAN_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    HUMAN_PROMPT,
    RAG_QUERIES,
    build_system_prompt,
)
from app.application.services.user_interactions.checklist_service.checklist_service_exceptions import \
    ChecklistServiceException
from app.application.services.user_interactions.checklist_service.checklist_service_interface import \
    ChecklistServiceInterface
from app.application.services.user_interactions.checklist_service.checklist_settings import ChecklistSettings
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
from app.domain.dtos.user_interactions.checklist.checklist_request import ChecklistGenerateRequest, ChecklistMode
from app.domain.dtos.user_interactions.checklist.checklist_response import ChecklistGenerateResponse, ChecklistItem
from app.domain.dtos.user_interactions.checklist.checklist_stream_events import (
    ChecklistStreamComplete,
    ChecklistStreamError,
    ChecklistStreamEvent,
    ChecklistStreamProgress,
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
    ChecklistServiceException,
    UnauthorizedException,
)


def _clean(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _parse_items(raw_items: list, settings: ChecklistSettings) -> list[ChecklistItem]:
    items: list[ChecklistItem] = []
    for entry in raw_items[:settings.max_items]:
        if not isinstance(entry, dict):
            continue
        text = _clean(entry.get("text", ""), settings.max_item_text_chars)
        if not text:
            continue
        items.append(
            ChecklistItem(
                section=_clean(entry.get("section", "General"), settings.max_section_chars) or "General",
                order=max(1, int(entry.get("order", 1))),
                text=text,
                is_checked=False,
                notes="",
            )
        )
    return items


def _fallback_items(raw: str, settings: ChecklistSettings) -> tuple[str, list[ChecklistItem]]:
    lines = [ln.strip().lstrip("•-*0123456789.) ") for ln in raw.splitlines() if ln.strip()]
    items = [
        ChecklistItem(
            section="Procedimiento",
            order=i + 1,
            text=ln[:settings.max_item_text_chars],
            is_checked=False,
            notes="",
        )
        for i, ln in enumerate(lines[:settings.max_items])
        if ln
    ]
    return "Checklist de procedimiento", items


def _parse_llm_output(raw: str, settings: ChecklistSettings) -> tuple[str, list[ChecklistItem]]:
    try:
        data = parse_json_object(raw)
        title = _clean(data.get("title", "Checklist"), settings.max_title_chars) or "Checklist"
        items = _parse_items(data.get("items", []), settings)
        if not items:
            raise ValueError("No se encontraron ítems válidos en la respuesta.")
        return title, items
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("LLM did not return valid JSON; falling back to line-by-line parsing: %s", e)
        return _fallback_items(raw, settings)


class ChecklistService(ChecklistServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            generation_settings: GenerationSettings | None = None,
            checklist_settings: ChecklistSettings | None = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._generation_settings = generation_settings or GenerationSettings()
        self._checklist_settings = checklist_settings or ChecklistSettings()
        self._reformulation_processor = QueryReformulationProcessor(
            self._generation_settings, ollama_llm_facade, ollama_llm_invoker
        )
        self._context_processor = ContextRetrievalProcessor(self._generation_settings, document_context_provider)
        self._attached_processor = AttachedDocumentsProcessor(self._generation_settings, document_context_provider)
        self._reduction_processor = ContextReductionProcessor(
            self._generation_settings, ollama_llm_facade, ollama_llm_invoker
        )
        logger.info("ChecklistService initialized")

    def _build_state(
            self,
            request: ChecklistGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> GenerationState:
        return GenerationState.create(
            messages=request.messages,
            chat_id=request.chat_id,
            is_rag=request.mode == ChecklistMode.RAG,
            authenticated_user=authenticated_user,
            document_ids=request.document_ids,
        )

    async def _gather_context(self, state: GenerationState) -> None:
        await self._attached_processor.run(state)
        if state.is_rag:
            await self._reformulation_processor.run(state)
            await self._context_processor.run(state, RAG_QUERIES)
        await self._reduction_processor.run(state, EXTRACTION_SYSTEM_PROMPT, EXTRACTION_HUMAN_PROMPT)

    async def _invoke(self, state: GenerationState, request: ChecklistGenerateRequest) -> str:
        context_block = build_context_block(
            state, self._generation_settings.max_context_chars, self._generation_settings.attached_reserve_ratio
        )
        llm_messages = build_generation_messages(
            augment_system_prompt(build_system_prompt(self._checklist_settings), request.system_prompt, request.response_style),
            HUMAN_PROMPT,
            state,
            self._generation_settings.history_messages_window,
            context_block,
        )
        llm = await self._ollama_llm_facade.get_llm_json()
        raw = (await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_messages)).strip()
        if not raw:
            raise ChecklistServiceException(
                "El modelo de lenguaje devolvió una respuesta vacía.", status_code=502
            )
        return raw

    @staticmethod
    def _build_response(
            state: GenerationState,
            title: str,
            items: list[ChecklistItem],
            raw: str,
    ) -> ChecklistGenerateResponse:
        assistant_msg = Message(role=MessageRole.assistant, content=raw)
        return ChecklistGenerateResponse(
            title=title,
            items=items,
            messages=[*state.messages, assistant_msg],
            fragments=state.all_fragments,
        )

    async def generate(
            self,
            request: ChecklistGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ChecklistGenerateResponse:
        logger.info(
            "Checklist generation initiated",
            extra={"user_id": authenticated_user.id, "mode": request.mode},
        )
        try:
            state = self._build_state(request, authenticated_user)
            await self._gather_context(state)

            raw = await self._invoke(state, request)
            title, items = _parse_llm_output(raw, self._checklist_settings)
            if not items:
                raise ChecklistServiceException(
                    "No se pudieron extraer ítems de la respuesta del modelo.", status_code=502
                )

            logger.info(
                "Checklist generation completed",
                extra={
                    "user_id": authenticated_user.id,
                    "items_count": len(items),
                    "fragments_used": len(state.all_fragments),
                },
            )
            return self._build_response(state, title, items, raw)

        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during checklist generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise ChecklistServiceException(
                "Error inesperado durante la generación de la checklist.", status_code=500
            ) from e

    async def generate_stream(
            self,
            request: ChecklistGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[ChecklistStreamEvent]:
        try:
            state = self._build_state(request, authenticated_user)
            if state.document_ids:
                yield ChecklistStreamProgress(
                    step="loading_documents",
                    message="Leyendo documentos adjuntos...",
                )
                await self._attached_processor.run(state)
                if state.is_rag:
                    yield ChecklistStreamProgress(
                        step="searching",
                        message="Buscando contexto adicional en la base de conocimiento...",
                    )
                    await self._reformulation_processor.run(state)
                    await self._context_processor.run(state, RAG_QUERIES)
            elif state.is_rag:
                yield ChecklistStreamProgress(
                    step="searching",
                    message="Buscando información relevante en los documentos...",
                )
                await self._reformulation_processor.run(state)
                await self._context_processor.run(state, RAG_QUERIES)
            await self._reduction_processor.run(state, EXTRACTION_SYSTEM_PROMPT, EXTRACTION_HUMAN_PROMPT)

            yield ChecklistStreamProgress(step="generation", message="Estructurando pasos y organizando la checklist...")

            raw = await self._invoke(state, request)
            title, items = _parse_llm_output(raw, self._checklist_settings)
            if not items:
                raise ChecklistServiceException(
                    "No se pudieron extraer ítems de la respuesta del modelo.", status_code=502
                )

            yield ChecklistStreamComplete(result=self._build_response(state, title, items, raw))
        except _KNOWN_EXCEPTIONS as e:
            logger.warning(
                "Known error during checklist stream generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            yield ChecklistStreamError(message=str(e), code=type(e).__name__)
        except Exception as e:
            logger.exception(
                "Unexpected error during checklist stream generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            yield ChecklistStreamError(
                message="Error inesperado durante la generación de la checklist.",
                code="internal_error",
            )


async def get_checklist_service(request: Request) -> ChecklistServiceInterface:
    try:
        return request.app.state.checklist_service
    except AttributeError:
        logger.error("ChecklistService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Checklist service is not available",
        )
