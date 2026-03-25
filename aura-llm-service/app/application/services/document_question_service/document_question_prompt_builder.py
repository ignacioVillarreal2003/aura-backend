import logging
from typing import List
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.application.services.document_question_service.prompts.context_selection_prompt import (
    CONTEXT_SELECTION_PROMPT
)
from app.application.services.document_question_service.prompts.default_style_prompt import (
    CONCISE_MODE,
    EXPLANATORY_MODE,
    FORMAL_MODE,
    LEARNING_GUIDELINES,
)
from app.application.services.document_question_service.prompts.fallback_prompt import FALLBACK_PROMPT
from app.application.services.document_question_service.prompts.generation_prompt import GENERATION_PROMPT
from app.application.services.document_question_service.prompts.query_rewrite_prompt import QUERY_REWRITE_PROMPT
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)

_HISTORY_WINDOW = 5  # messages kept for prompt context


class DocumentQuestionPromptBuilder:
    def build_query_rewrite_prompt(
            self,
            question: str,
            history_messages: List[Message]
    ) -> List[BaseMessage]:
        history_text = self._format_history_as_text(history_messages)
        content = QUERY_REWRITE_PROMPT.format(
            history=history_text or "Sin historial previo.",
            query=question
        )
        return [HumanMessage(content=content)]

    def build_context_selection_prompt(
            self,
            query: str,
            fragments: List[str],
            max_fragments: int
    ) -> List[BaseMessage]:
        numbered_chunks = "\n\n".join(
            f"[{i}] {fragment}" for i, fragment in enumerate(fragments)
        )
        content = CONTEXT_SELECTION_PROMPT.format(
            query=query,
            chunks=numbered_chunks,
            max_fragments=max_fragments
        )
        return [HumanMessage(content=content)]

    def build_generation_prompt(
            self,
            question: str,
            context_fragments: List[str],
            history_messages: List[Message],
            system_prompt: str
    ) -> List[BaseMessage]:
        style_block = self._build_style_block()
        full_system = f"{system_prompt}\n\n{style_block}"
        context = self._format_context(context_fragments)

        return [
            SystemMessage(content=full_system),
            *self._build_history_messages(history_messages),
            HumanMessage(
                content=GENERATION_PROMPT.format(
                    query=question,
                    context=context,
                )
            ),
        ]

    def build_fallback_prompt(
            self,
            question: str,
            system_prompt: str,
    ) -> List[BaseMessage]:
        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=FALLBACK_PROMPT.format(query=question))
        ]

    @staticmethod
    def _build_style_block() -> str:
        return (
            f"{LEARNING_GUIDELINES}\n\n"
            f"{CONCISE_MODE}\n\n"
            f"{EXPLANATORY_MODE}\n\n"
            f"{FORMAL_MODE}"
        )

    @staticmethod
    def _format_context(fragments: List[str]) -> str:
        if not fragments:
            return "No se encontró información relevante en los documentos."
        return "\n\n---\n\n".join(fragments)

    @staticmethod
    def _build_history_messages(history_messages: List[Message]) -> List[BaseMessage]:
        if not history_messages:
            return []

        tail = history_messages[-_HISTORY_WINDOW:]
        messages: List[BaseMessage] = []

        for msg in tail:
            if msg.role == MessageRole.human:
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.assistant:
                messages.append(AIMessage(content=msg.content))

        return messages

    @staticmethod
    def _format_history_as_text(history_messages: List[Message]) -> str:
        if not history_messages:
            return ""

        tail = history_messages[-_HISTORY_WINDOW:]
        lines: List[str] = []

        for msg in tail:
            role_label = "Usuario" if msg.role == MessageRole.human else "Asistente"
            lines.append(f"{role_label}: {msg.content}")

        return "\n".join(lines)
