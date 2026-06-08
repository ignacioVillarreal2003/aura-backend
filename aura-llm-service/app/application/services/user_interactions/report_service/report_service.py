import logging
from collections.abc import AsyncIterator
from fastapi import HTTPException, Request, status

from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.user_interactions.report_service.report_service_exceptions import ReportServiceException
from app.application.services.user_interactions.report_service.report_service_interface import ReportServiceInterface
from app.application.services.user_interactions.report_service.report_settings import ReportSettings
from app.application.services.user_interactions.report_service.report_prompt import (
    EXTRACTION_HUMAN_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    HUMAN_PROMPT,
    RAG_QUERIES,
    build_system_prompt,
)
from app.application.services.generation_shared.generation_messages import (
    build_context_block,
    build_generation_messages,
)
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
from app.domain.dtos.message import Message
from app.domain.dtos.user_interactions.report.report_request import ReportGenerateRequest, ReportMode, ReportType
from app.domain.dtos.user_interactions.report.report_response import ReportGenerateResponse
from app.domain.dtos.user_interactions.report.report_stream_events import (
    ReportStreamComplete,
    ReportStreamError,
    ReportStreamEvent,
    ReportStreamProgress,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_REPORT_GENERATION_MESSAGES: dict[ReportType, str] = {
    ReportType.SITREP: "Redactando el informe de situación (SITREP)...",
    ReportType.INTSUM: "Redactando el resumen de inteligencia (INTSUM)...",
    ReportType.OPORD: "Redactando la orden de operaciones (OPORD)...",
}

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    ReportServiceException,
    UnauthorizedException,
)


class ReportService(ReportServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            generation_settings: GenerationSettings | None = None,
            report_settings: ReportSettings | None = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._generation_settings = generation_settings or GenerationSettings()
        self._report_settings = report_settings or ReportSettings()
        self._reformulation_processor = QueryReformulationProcessor(
            self._generation_settings, ollama_llm_facade, ollama_llm_invoker
        )
        self._context_processor = ContextRetrievalProcessor(self._generation_settings, document_context_provider)
        self._attached_processor = AttachedDocumentsProcessor(self._generation_settings, document_context_provider)
        self._reduction_processor = ContextReductionProcessor(
            self._generation_settings, ollama_llm_facade, ollama_llm_invoker
        )
        logger.info("ReportService initialized")

    def _build_state(
            self,
            request: ReportGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> GenerationState:
        return GenerationState.create(
            messages=request.messages,
            chat_id=request.chat_id,
            is_rag=request.mode == ReportMode.RAG,
            authenticated_user=authenticated_user,
            document_ids=request.document_ids,
        )

    async def _gather_context(self, state: GenerationState, report_type: ReportType) -> None:
        await self._attached_processor.run(state)
        if state.is_rag:
            await self._reformulation_processor.run(state)
            await self._context_processor.run(state, RAG_QUERIES[report_type])
        await self._reduction_processor.run(state, EXTRACTION_SYSTEM_PROMPT, EXTRACTION_HUMAN_PROMPT)

    async def _invoke(self, state: GenerationState, report_type: ReportType) -> str:
        context_block = build_context_block(
            state, self._generation_settings.max_context_chars, self._generation_settings.attached_reserve_ratio
        )
        llm_messages = build_generation_messages(
            build_system_prompt(report_type),
            HUMAN_PROMPT,
            state,
            self._generation_settings.history_messages_window,
            context_block,
        )
        llm = await self._ollama_llm_facade.get_llm_base()
        content = (await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_messages)).strip()
        if not content:
            raise ReportServiceException(
                "El modelo de lenguaje devolvió una respuesta vacía.", status_code=502
            )
        return content[:self._report_settings.max_content_chars]

    @staticmethod
    def _build_response(
            state: GenerationState,
            report_type: ReportType,
            content: str,
    ) -> ReportGenerateResponse:
        assistant_msg = Message(role=MessageRole.assistant, content=content)
        return ReportGenerateResponse(
            report_type=report_type,
            content=content,
            messages=[*state.messages, assistant_msg],
            fragments=state.all_fragments,
        )

    async def generate(
            self,
            request: ReportGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ReportGenerateResponse:
        logger.info(
            "Report generation initiated",
            extra={
                "user_id": authenticated_user.id,
                "report_type": request.report_type,
                "mode": request.mode,
            },
        )
        try:
            state = self._build_state(request, authenticated_user)
            await self._gather_context(state, request.report_type)

            content = await self._invoke(state, request.report_type)

            logger.info(
                "Report generation completed",
                extra={
                    "user_id": authenticated_user.id,
                    "report_type": request.report_type,
                    "fragments_used": len(state.all_fragments),
                },
            )
            return self._build_response(state, request.report_type, content)

        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during report generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise ReportServiceException(
                "Error inesperado durante la generación del informe.", status_code=500
            ) from e

    async def generate_stream(
            self,
            request: ReportGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[ReportStreamEvent]:
        try:
            state = self._build_state(request, authenticated_user)
            if state.document_ids:
                yield ReportStreamProgress(
                    step="loading_documents",
                    message="Leyendo documentos adjuntos...",
                )
                await self._attached_processor.run(state)
                if state.is_rag:
                    yield ReportStreamProgress(
                        step="searching",
                        message="Buscando contexto adicional en la base de conocimiento...",
                    )
                    await self._reformulation_processor.run(state)
                    await self._context_processor.run(state, RAG_QUERIES[request.report_type])
            elif state.is_rag:
                yield ReportStreamProgress(
                    step="searching",
                    message="Buscando información relevante en los documentos...",
                )
                await self._reformulation_processor.run(state)
                await self._context_processor.run(state, RAG_QUERIES[request.report_type])
            await self._reduction_processor.run(state, EXTRACTION_SYSTEM_PROMPT, EXTRACTION_HUMAN_PROMPT)

            yield ReportStreamProgress(
                step="generation",
                message=_REPORT_GENERATION_MESSAGES[request.report_type],
            )

            content = await self._invoke(state, request.report_type)

            yield ReportStreamComplete(result=self._build_response(state, request.report_type, content))
        except _KNOWN_EXCEPTIONS as e:
            logger.warning(
                "Known error during report stream generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            yield ReportStreamError(message=str(e), code=type(e).__name__)
        except Exception as e:
            logger.exception(
                "Unexpected error during report stream generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            yield ReportStreamError(
                message="Error inesperado durante la generación del informe.",
                code="internal_error",
            )


async def get_report_service(request: Request) -> ReportServiceInterface:
    try:
        return request.app.state.report_service
    except AttributeError:
        logger.error("ReportService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Report service is not available",
        )
