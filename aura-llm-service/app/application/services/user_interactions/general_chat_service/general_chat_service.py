import logging
from collections.abc import AsyncIterator

from app.application.authorization.exceptions.authorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.user_interactions.general_chat_service.general_chat_service_exceptions import (
    GeneralChatServiceException,
)
from app.application.services.user_interactions.general_chat_service.general_chat_service_interface import (
    GeneralChatServiceInterface,
)
from app.application.services.user_interactions.general_chat_service.general_chat_prompt import (
    EXTRACTION_HUMAN_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    HUMAN_PROMPT,
    RAG_QUERIES,
    build_system_prompt,
)
from app.application.services.user_interactions.general_chat_service.general_chat_settings import GeneralChatSettings
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
from app.domain.dtos.message import Message
from app.domain.dtos.user_interactions.general_chat.general_chat_request import GeneralChatMode, GeneralChatRequest
from app.domain.dtos.user_interactions.general_chat.general_chat_response import GeneralChatResponse
from app.domain.dtos.user_interactions.general_chat.general_chat_stream_events import (
    GeneralChatStreamComplete,
    GeneralChatStreamDelta,
    GeneralChatStreamError,
    GeneralChatStreamEvent,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_streaming_invoker_interface import (
    OllamaLLMStreamingInvokerInterface,
)

logger = logging.getLogger(__name__)

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    GeneralChatServiceException,
    UnauthorizedException,
)


class GeneralChatService(GeneralChatServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            ollama_llm_streaming_invoker: OllamaLLMStreamingInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            generation_settings: GenerationSettings | None = None,
            general_chat_settings: GeneralChatSettings | None = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._ollama_llm_streaming_invoker = ollama_llm_streaming_invoker
        self._generation_settings = generation_settings or GenerationSettings()
        self._general_chat_settings = general_chat_settings or GeneralChatSettings()
        self._reformulation_processor = QueryReformulationProcessor(
            self._generation_settings, ollama_llm_facade, ollama_llm_invoker
        )
        self._context_processor = ContextRetrievalProcessor(self._generation_settings, document_context_provider)
        self._attached_processor = AttachedDocumentsProcessor(self._generation_settings, document_context_provider)
        self._reduction_processor = ContextReductionProcessor(
            self._generation_settings, ollama_llm_facade, ollama_llm_invoker
        )
        logger.info("GeneralChatService initialized")

    def _build_state(
            self,
            request: GeneralChatRequest,
            authenticated_user: AuthenticatedUser,
    ) -> GenerationState:
        return GenerationState.create(
            messages=request.messages,
            chat_id=request.chat_id,
            is_rag=request.mode == GeneralChatMode.RAG,
            authenticated_user=authenticated_user,
            document_ids=request.document_ids,
        )

    async def _gather_context(self, state: GenerationState) -> None:
        await self._attached_processor.run(state)
        if state.is_rag:
            await self._reformulation_processor.run(state)
            await self._context_processor.run(state, RAG_QUERIES)
        await self._reduction_processor.run(state, EXTRACTION_SYSTEM_PROMPT, EXTRACTION_HUMAN_PROMPT)

    def _build_llm_messages(
            self,
            state: GenerationState,
            custom_system_prompt: str | None,
            response_style: str | None = None,
    ) -> list:
        context_block = build_context_block(
            state, self._generation_settings.max_context_chars, self._generation_settings.attached_reserve_ratio
        )
        system_prompt = augment_system_prompt(
            build_system_prompt(self._general_chat_settings),
            custom_system_prompt,
            response_style,
        )
        return build_generation_messages(
            system_prompt,
            HUMAN_PROMPT,
            state,
            self._generation_settings.history_messages_window,
            context_block,
        )

    def _build_response(self, state: GenerationState, answer: str) -> GeneralChatResponse:
        answer = answer[:self._general_chat_settings.max_response_chars]
        assistant_msg = Message(role=MessageRole.assistant, content=answer)
        return GeneralChatResponse(
            answer=answer,
            messages=[*state.messages, assistant_msg],
            fragments=state.all_fragments,
        )

    async def execute_general_chat(
            self,
            general_chat_request: GeneralChatRequest,
            authenticated_user: AuthenticatedUser,
    ) -> GeneralChatResponse:
        logger.info(
            "General chat execution initiated",
            extra={"user_id": authenticated_user.id, "mode": general_chat_request.mode},
        )
        try:
            state = self._build_state(general_chat_request, authenticated_user)
            await self._gather_context(state)

            llm_messages = self._build_llm_messages(
                state, general_chat_request.system_prompt, general_chat_request.response_style
            )
            llm = await self._ollama_llm_facade.get_llm_base()
            answer = (await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_messages)).strip()
            if not answer:
                raise GeneralChatServiceException("El modelo de lenguaje devolvió una respuesta vacía.")

            logger.info(
                "General chat execution completed",
                extra={"user_id": authenticated_user.id, "fragments_used": len(state.all_fragments)},
            )
            return self._build_response(state, answer)

        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during general chat execution",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise GeneralChatServiceException(
                "Error inesperado al procesar la solicitud de chat."
            ) from e

    async def execute_general_chat_stream(
            self,
            general_chat_request: GeneralChatRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[GeneralChatStreamEvent]:
        try:
            state = self._build_state(general_chat_request, authenticated_user)

            await self._gather_context(state)

            llm_messages = self._build_llm_messages(
                state, general_chat_request.system_prompt, general_chat_request.response_style
            )
            llm = await self._ollama_llm_facade.get_llm_base()

            accumulated = ""
            try:
                async for delta in self._ollama_llm_streaming_invoker.stream_llm_content(llm, llm_messages):
                    accumulated += delta
                    yield GeneralChatStreamDelta(text=delta)
            except LLMInvocationError as e:
                logger.exception("LLM error during general chat streaming")
                yield GeneralChatStreamError(message=str(e), code=type(e).__name__)
                return
            except Exception as e:
                logger.exception(
                    "Error during general chat streaming",
                    extra={"error_type": type(e).__name__},
                )
                yield GeneralChatStreamError(
                    message="Error al invocar el modelo de lenguaje.",
                    code="StreamGeneralChatError",
                )
                return

            answer = accumulated.strip()
            if not answer:
                logger.warning("Stream produced no text; falling back to sync invocation")
                try:
                    answer = (
                        await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_messages)
                    ).strip()
                    if answer:
                        yield GeneralChatStreamDelta(text=answer)
                except Exception:
                    logger.exception("Fallback sync invocation failed")
                    yield GeneralChatStreamError(
                        message="El modelo de lenguaje devolvió una respuesta vacía.",
                        code="GeneralChatEmptyResponse",
                    )
                    return

            if not answer:
                yield GeneralChatStreamError(
                    message="El modelo de lenguaje devolvió una respuesta vacía.",
                    code="GeneralChatEmptyResponse",
                )
                return

            yield GeneralChatStreamComplete(result=self._build_response(state, answer))

        except _KNOWN_EXCEPTIONS as e:
            logger.warning(
                "Known error during general chat stream",
                extra={"error_type": type(e).__name__},
            )
            yield GeneralChatStreamError(message=str(e), code=type(e).__name__)
        except Exception as e:
            logger.exception(
                "Unexpected error during general chat stream",
                extra={"error_type": type(e).__name__},
            )
            yield GeneralChatStreamError(
                message="Error inesperado al procesar la solicitud de chat.",
                code="GeneralChatStreamError",
            )

