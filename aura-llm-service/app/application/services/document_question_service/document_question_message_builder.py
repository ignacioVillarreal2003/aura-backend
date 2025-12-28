import logging
from typing import Sequence, List, Optional
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    BaseMessage,
    AIMessage
)

from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)


class DocumentQuestionMessageBuilder:
    @staticmethod
    def build_system_message(system_prompt: str) -> SystemMessage:
        return SystemMessage(content=system_prompt)

    @staticmethod
    def build_context_message(fragments: Sequence[str]) -> HumanMessage:
        if not fragments:
            return HumanMessage(
                content="No se encontró contexto relevante en los documentos."
            )

        fragments_joined = "\n\n---\n\n".join(fragments)

        return HumanMessage(
            content=f"Contexto relevante extraído de documentos:\n\n{fragments_joined}"
        )

    @staticmethod
    def build_history_messages(messages: List[Message]) -> List[BaseMessage]:
        history: List[BaseMessage] = []

        for message in messages:
            langchain_message = DocumentQuestionMessageBuilder._convert_message_to_langchain(message)

            if langchain_message:
                history.append(langchain_message)

        return history

    @staticmethod
    def _convert_message_to_langchain(message: Message) -> Optional[BaseMessage]:
        if message.role == MessageRole.human:
            return HumanMessage(content=message.content)

        elif message.role == MessageRole.assistant:
            return AIMessage(content=message.content)

        else:
            logger.warning(
                "Unknown message role in history, skipping",
                extra={
                    "role": str(message.role),
                    "content_preview": message.content[:50]
                }
            )
            return None

    @staticmethod
    def build_question_message(question: str) -> HumanMessage:
        return HumanMessage(
            content=f"Basado en el contexto proporcionado, responde a la siguiente pregunta:\n{question}"
        )

    @staticmethod
    def build_complete_input(system_prompt: str,
                             fragments: Sequence[str],
                             messages: List[Message],
                             question: str) -> List[BaseMessage]:
        llm_input: List[BaseMessage] = []

        llm_input.append(DocumentQuestionMessageBuilder.build_system_message(system_prompt))
        llm_input.append(DocumentQuestionMessageBuilder.build_context_message(fragments))
        llm_input.extend(DocumentQuestionMessageBuilder.build_history_messages(messages))
        llm_input.append(DocumentQuestionMessageBuilder.build_question_message(question))

        return llm_input
