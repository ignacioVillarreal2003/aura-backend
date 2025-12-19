import logging
from typing import List

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import Runnable

from app.application.exceptions.document_question_service_exceptions import DocumentQuestionServiceError
from app.application.ollama_configurator.ollama_configurator import OllamaConfigurator
from app.application.services.fragment_retrieval_service import FragmentRetrievalService
from app.domain.dtos.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question_response import DocumentQuestionResponse
from app.domain.dtos.message import Message
from app.infrastructure.http.http_client import HttpClient

logger = logging.getLogger(__name__)


class DocumentQuestionService:
    SYSTEM_PROMPT: str = (
        "Eres un asistente útil que responde únicamente basándose en el contexto proporcionado. "
        "La respuesta debe estar en formato Markdown e incluir títulos (`#`), subtítulos (`##`), "
        "listas (`-`), negritas (`**`) y tablas cuando corresponda. "
        "Si el contexto no contiene suficiente información, indica claramente que la información "
        "no está disponible y ofrece una respuesta general relacionada al tema sin inventar datos."
    )

    def __init__(self,
                 http_client: HttpClient,
                 ollama_configurator: OllamaConfigurator,
                 fragment_retrieval_service: FragmentRetrievalService,
                 max_fragments: int = 3) -> None:
        self.http_client = http_client
        self.ollama_configurator = ollama_configurator
        self.fragment_retrieval_service = fragment_retrieval_service
        self.max_fragments = max_fragments

        self.llm: Runnable = self.ollama_configurator.get_llm_base()

    async def execute_document_question(self,
                                        document_question_request: DocumentQuestionRequest) -> DocumentQuestionResponse:
        logger.info("Executing document question")

        try:
            fragments = await self.fragment_retrieval_service.get_fragments(
                question=document_question_request.question,
                max_fragments=self.max_fragments
            )

            llm_input = self._build_llm_input(
                fragments=fragments,
                messages=document_question_request.messages,
                question=document_question_request.question
            )

            result = await self._invoke_llm(llm_input)

            answer = self._extract_answer(result)

            logger.info("Document question executed successfully")

            return DocumentQuestionResponse(answer=answer)

        except Exception:
            logger.exception("Unexpected error during document question execution")
            raise DocumentQuestionServiceError("Unexpected internal error executing document question")

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
        return SystemMessage(content=self.SYSTEM_PROMPT)

    def _build_context_message(self,
                               fragments: List[str]) -> HumanMessage:
        if not fragments:
            return HumanMessage(content="No se encontró contexto relevante en los documentos.")

        fragments_joined = "\n\n---\n\n".join(fragments)

        return HumanMessage(content=f"Contexto relevante extraído de documentos:\n\n{fragments_joined}")

    def _build_history_messages(self,
                                messages: List[Message]) -> List[BaseMessage]:
        history: List[BaseMessage] = []

        for message in messages:
            if message.role == "user":
                history.append(HumanMessage(content=message.content))
            elif message.role == "assistant":
                history.append(AIMessage(content=message.content))
            else:
                logger.warning(f"Unknown message role: {message.role}, skipping message")

        return history

    def _build_question_message(self,
                                question: str) -> HumanMessage:
        return HumanMessage(
            content=f"Basado en el contexto proporcionado, responde a la siguiente pregunta:\n{question}")

    async def _invoke_llm(self,
                          llm_input: List[BaseMessage]) -> BaseMessage:
        logger.debug("Invoking LLM")

        try:
            result: BaseMessage = await self.llm.ainvoke(llm_input)

            if not isinstance(result, BaseMessage):
                logger.error("LLM returned invalid type")
                raise DocumentQuestionServiceError("LLM returned invalid type")

            return result

        except Exception:
            logger.error("LLM invocation failed")
            raise DocumentQuestionServiceError(f"LLM invocation failed")

    def _extract_answer(self,
                        result: BaseMessage) -> str:
        content = result.content

        if isinstance(content, str):
            return content

        logger.warning("LLM returned non-string content")
        return str(content)
