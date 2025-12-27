import logging
from typing import List
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import Runnable

from app.application.exceptions.app_exceptions import ValidationError
from app.application.exceptions.context_provider_exception import ContextRetrievalByQuestionError
from app.application.exceptions.document_question_service_exceptions import DocumentQuestionServiceError
from app.application.exceptions.ollama_configurator_exceptions import LLMInvocationError
from app.application.llm_configurator.interfaces.llm_configurator_interface import LLMConfiguratorInterface
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question_response import DocumentQuestionResponse
from app.domain.dtos.message import Message
from app.infrastructure.providers.context_provider import ContextProvider
from app.infrastructure.providers.interfaces.context_provider_interface import ContextProviderInterface

logger = logging.getLogger(__name__)


class DocumentQuestionService:
    DEFAULT_MAX_FRAGMENTS: int = 3
    MIN_QUESTION_LENGTH: int = 1
    DEFAULT_MAX_QUESTION_LENGTH: int = 1000
    MAX_QUESTION_LENGTH: int = 10000
    MIN_HISTORY_COUNT: int = 1
    DEFAULT_MAX_HISTORY_COUNT: int = 3
    MAX_HISTORY_COUNT: int = 6

    SYSTEM_PROMPT: str = (
        "Eres un asistente útil que responde únicamente basándose en el contexto proporcionado. "
        "La respuesta debe estar en formato Markdown e incluir títulos (`#`), subtítulos (`##`), "
        "listas (`-`), negritas (`**`) y tablas cuando corresponda. "
        "Si el contexto no contiene suficiente información, indica claramente que la información "
        "no está disponible y ofrece una respuesta general relacionada al tema sin inventar datos."
    )

    def __init__(self,
                 llm_configurator: LLMConfiguratorInterface,
                 context_provider: ContextProviderInterface,
                 max_fragments: int = DEFAULT_MAX_FRAGMENTS,
                 max_question_length: int = DEFAULT_MAX_QUESTION_LENGTH,
                 max_history_count: int = DEFAULT_MAX_HISTORY_COUNT) -> None:
        self._llm_configurator = llm_configurator
        self._context_provider = context_provider
        self._max_fragments = max_fragments
        self._max_question_length = max_question_length
        self._max_history_count = max_history_count

        self._validate_configuration()

        self._llm: Runnable = self._llm_configurator.get_llm_base()

        logger.debug("DocumentQuestionService initialized")

    async def execute_document_question(self,
                                        document_question_request: DocumentQuestionRequest) -> DocumentQuestionResponse:
        self._validate_request(document_question_request)

        logger.info(
            "Executing document question",
            extra={
                "question": document_question_request.question
            }
        )

        try:
            fragments = await self._context_provider.retrieve_fragments_by_question(
                question=document_question_request.question,
                max_fragments=self._max_fragments
            )

            llm_input = self._build_llm_input(
                fragments=fragments,
                messages=document_question_request.messages or [],
                question=document_question_request.question
            )

            answer = await self._llm_configurator.call_llm_text(
                llm=self._llm,
                llm_input=llm_input
            )

            logger.info(
                "Document question executed successfully",
                extra={
                    "question": document_question_request.question,
                    "answer": answer
                }
            )

            return DocumentQuestionResponse(answer=answer)

        except (ValidationError,
                ContextRetrievalByQuestionError,
                LLMInvocationError,
                DocumentQuestionServiceError):
            raise

        except Exception as e:
            logger.exception(
                "Unexpected error during document question execution",
                extra={
                    "error_type": type(e).__name__,
                    "question": document_question_request.question
                }
            )
            raise DocumentQuestionServiceError("Unexpected internal error executing document question") from e

    def _validate_configuration(self) -> None:
        if self._max_question_length < self.MIN_QUESTION_LENGTH or self._max_question_length > self.MAX_QUESTION_LENGTH:
            raise ValidationError(
                f"Configured max_question_length must be between {self.MIN_QUESTION_LENGTH} and {self.MAX_QUESTION_LENGTH}",
                status_code=500
            )

        if self._max_history_count < self.MIN_HISTORY_COUNT or self._max_history_count > self.MAX_HISTORY_COUNT:
            raise ValidationError(
                f"Configured max_history_count must be between {self.MIN_HISTORY_COUNT} and {self.MAX_HISTORY_COUNT}",
                status_code=500
            )

    def _validate_request(self, request: DocumentQuestionRequest) -> None:
        if not request.question or not request.question.strip():
            raise ValidationError(
                "Question cannot be empty",
                status_code=400
            )
        question_length = len(request.question.strip())
        if question_length < self.MIN_QUESTION_LENGTH or question_length > self._max_question_length:
            raise ValidationError(
                f"Question length must be between {self.MIN_QUESTION_LENGTH} and {self._max_question_length} characters",
                status_code=400
            )

        if request.messages is not None:
            history_count = len(request.messages)
            if history_count < self.MIN_HISTORY_COUNT or history_count > self._max_history_count:
                raise ValidationError(
                    f"Message history size must be between {self.MIN_HISTORY_COUNT} and {self._max_history_count} messages",
                    status_code=400
                )

    def _build_llm_input(self,
                         fragments: List[str],
                         messages: List[Message],
                         question: str) -> List[BaseMessage]:
        llm_input: List[BaseMessage] = []

        llm_input.append(self._build_system_message())
        llm_input.append(self._build_context_message(fragments))
        llm_input.extend(self._build_history_messages(messages))
        llm_input.append(self._build_question_message(question))

        return llm_input

    def _build_system_message(self) -> SystemMessage:
        return SystemMessage(
            content=self.SYSTEM_PROMPT
        )

    def _build_context_message(self,
                               fragments: List[str]) -> HumanMessage:
        if not fragments:
            return HumanMessage(
                content="No se encontró contexto relevante en los documentos."
            )

        fragments_joined = "\n\n---\n\n".join(fragments)

        return HumanMessage(
            content=f"Contexto relevante extraído de documentos:\n\n{fragments_joined}"
        )

    def _build_history_messages(self,
                                messages: List[Message]) -> List[BaseMessage]:
        history: List[BaseMessage] = []

        for message in messages:
            if message.role == MessageRole.human:
                history.append(
                    HumanMessage(
                        content=message.content
                    )
                )
            elif message.role == MessageRole.assistant:
                history.append(
                    AIMessage(
                        content=message.content
                    )
                )
            else:
                logger.warning(
                    "Unknown message role in history",
                    extra={
                        "role": str(message.role)
                    }
                )

        return history

    def _build_question_message(self, question: str) -> HumanMessage:
        return HumanMessage(
            content=f"Basado en el contexto proporcionado, responde a la siguiente pregunta:\n{question}"
        )
