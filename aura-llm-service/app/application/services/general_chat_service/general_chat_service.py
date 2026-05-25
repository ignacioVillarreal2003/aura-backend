import logging
from collections.abc import AsyncIterator

from fastapi import HTTPException, Request, status
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.authorization.permissions import Permissions
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.general_chat_service.exceptions.general_chat_service_exceptions import (
    GeneralChatServiceException,
)
from app.application.services.general_chat_service.interfaces.general_chat_service_interface import (
    GeneralChatServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.general_chat.general_chat_request import GeneralChatRequest
from app.domain.dtos.general_chat.general_chat_response import GeneralChatResponse
from app.domain.dtos.general_chat.general_chat_stream_events import (
    GeneralChatStreamComplete,
    GeneralChatStreamDelta,
    GeneralChatStreamError,
    GeneralChatStreamEvent,
)
from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_CONTENT_CHARS
from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_streaming_invoker_interface import (
    OllamaLLMStreamingInvokerInterface,
)

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = (
    "Eres AURA, un asistente de inteligencia artificial útil, preciso y conciso. "
    "Responde siempre en el mismo idioma que el usuario utilice."
)


def _build_llm_input(request: GeneralChatRequest) -> list[BaseMessage]:
    system_prompt = (request.system_prompt or _DEFAULT_SYSTEM_PROMPT).strip()
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]

    for msg in request.messages:
        if msg.role == MessageRole.human:
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == MessageRole.assistant:
            messages.append(AIMessage(content=msg.content))

    return messages


def _build_response(request: GeneralChatRequest, answer: str) -> GeneralChatResponse:
    answer_message = Message(role=MessageRole.assistant, content=answer)
    return GeneralChatResponse(
        answer=answer,
        messages=[*request.messages, answer_message],
    )


class GeneralChatService(GeneralChatServiceInterface):
    _KNOWN_EXCEPTIONS = (
        RequestValidationException,
        GeneralChatServiceException,
        UnauthorizedException,
    )

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            ollama_llm_streaming_invoker: OllamaLLMStreamingInvokerInterface,
            authorizer: Authorizer,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._ollama_llm_streaming_invoker = ollama_llm_streaming_invoker
        self._authorizer = authorizer

    async def execute_general_chat(
            self,
            general_chat_request: GeneralChatRequest,
            authenticated_user: AuthenticatedUser,
    ) -> GeneralChatResponse:
        logger.info("General chat execution initiated")
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_GENERAL_CHAT}),
        )
        try:
            llm_input = _build_llm_input(general_chat_request)
            llm = await self._ollama_llm_facade.get_llm_base()
            answer = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
            answer = answer.strip()
            if not answer:
                raise GeneralChatServiceException("The language model returned an empty response.")
            if len(answer) > MAX_CONTENT_CHARS:
                answer = answer[:MAX_CONTENT_CHARS]
            logger.info("General chat execution completed")
            return _build_response(general_chat_request, answer)
        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during general chat execution",
                extra={"error_type": type(e).__name__},
            )
            raise GeneralChatServiceException(
                "Unexpected error while processing the chat request"
            ) from e

    async def execute_general_chat_stream(
            self,
            general_chat_request: GeneralChatRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[GeneralChatStreamEvent]:
        try:
            self._authorizer.require_permissions(
                authenticated_user=authenticated_user,
                required_permissions=frozenset({Permissions.LLM_GENERAL_CHAT}),
            )

            llm_input = _build_llm_input(general_chat_request)
            llm = await self._ollama_llm_facade.get_llm_base()

            accumulated = ""
            try:
                async for delta in self._ollama_llm_streaming_invoker.stream_llm_content(llm, llm_input):
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
                    message="Error invoking the language model",
                    code="StreamGeneralChatError",
                )
                return

            answer = accumulated.strip()
            if not answer:
                # Fallback to sync invocation when stream produced nothing
                logger.warning("General chat stream produced no text; falling back to sync invocation")
                try:
                    answer = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
                    answer = answer.strip()
                    if answer:
                        yield GeneralChatStreamDelta(text=answer)
                except Exception as e:
                    logger.exception("Fallback sync invocation also failed")
                    yield GeneralChatStreamError(
                        message="The language model returned an empty response.",
                        code="GeneralChatEmptyResponse",
                    )
                    return

            if not answer:
                yield GeneralChatStreamError(
                    message="The language model returned an empty response.",
                    code="GeneralChatEmptyResponse",
                )
                return

            if len(answer) > MAX_CONTENT_CHARS:
                answer = answer[:MAX_CONTENT_CHARS]

            yield GeneralChatStreamComplete(result=_build_response(general_chat_request, answer))

        except RequestValidationException as e:
            yield GeneralChatStreamError(message=e.message, code=e.code)
        except GeneralChatServiceException as e:
            yield GeneralChatStreamError(message=e.message, code=e.code)
        except UnauthorizedException as e:
            yield GeneralChatStreamError(message=str(e), code="Unauthorized")
        except Exception as e:
            logger.exception(
                "Unexpected error during general chat stream",
                extra={"error_type": type(e).__name__},
            )
            yield GeneralChatStreamError(
                message="Unexpected error while processing the chat request",
                code="GeneralChatStreamError",
            )


async def get_general_chat_service(request: Request) -> GeneralChatServiceInterface:
    try:
        return request.app.state.general_chat_service
    except AttributeError:
        logger.error("GeneralChatService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GeneralChatService is not available",
        )
