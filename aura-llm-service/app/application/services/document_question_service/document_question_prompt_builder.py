import logging
from typing import List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.application.services.document_question_service.prompts.default_style_prompt import LEARNING_GUIDELINES, \
    CONCISE_MODE, EXPLANATORY_MODE, FORMAL_MODE
from app.application.services.document_question_service.prompts.generation_prompt import GENERATION_PROMPT
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)


class DocumentQuestionPromptBuilder:
    def build_complete_prompt(
            self,
            question: str,
            context_fragments: List[str],
            history_messages: List[Message]
    ) -> List[BaseMessage]:

        system_prompt = self._build_system_prompt()

        context = self._format_context(context_fragments)

        return [
            SystemMessage(content=system_prompt),
            *self._build_history_messages(history_messages),
            self._build_generation_message(question, context)
        ]

    @staticmethod
    def _build_system_prompt() -> str:
        return f"""
    {LEARNING_GUIDELINES}

    {CONCISE_MODE}

    {EXPLANATORY_MODE}

    {FORMAL_MODE}
    """

    @staticmethod
    def _format_context(context_fragments: List[str]) -> str:
        if not context_fragments:
            return "No se encontró información relevante en los documentos."

        return "\n\n---\n\n".join(context_fragments)

    @staticmethod
    def _build_history_messages(history_messages: List[Message]) -> List[BaseMessage]:
        if not history_messages:
            return []

        history_messages = history_messages[-5:]

        messages = []

        for msg in history_messages:
            if msg.role == MessageRole.human:
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.assistant:
                messages.append(AIMessage(content=msg.content))

        return messages

    @staticmethod
    def _build_generation_message(question: str, context: str) -> HumanMessage:
        return HumanMessage(
            content=GENERATION_PROMPT.format(
                query=question,
                context=context
            )
        )