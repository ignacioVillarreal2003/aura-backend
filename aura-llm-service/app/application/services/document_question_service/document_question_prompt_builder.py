import logging
from typing import List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)


class DocumentQuestionPromptBuilder:
    def build_complete_prompt(
            self,
            system_prompt: str,
            question: str,
            context_fragments: List[str],
            history_messages: List[Message]
    ) -> List[BaseMessage]:
        logger.debug(
            "Building complete prompt",
            extra={
                "context_fragment_count": len(context_fragments),
                "history_message_count": len(history_messages)
            }
        )

        prompt_messages: List[BaseMessage] = [
            self._build_system_message(system_prompt),
            self._build_context_message(context_fragments),
            *self._build_history_messages(history_messages),
            self._build_question_message(question)
        ]

        logger.debug(
            "Complete prompt built successfully",
            extra={"total_messages": len(prompt_messages)},
        )

        return prompt_messages

    @staticmethod
    def _build_system_message(system_prompt: str) -> SystemMessage:
        return SystemMessage(content=system_prompt)

    @staticmethod
    def _build_context_message(context_fragments: Optional[List[str]]) -> HumanMessage:
        if not context_fragments:
            logger.debug("No context fragments provided — using empty context message")
            return HumanMessage(
                content="[CONTEXT]: No relevant information was found in the documents."
            )

        context_content = "\n\n---\n\n".join(
            f"Context fragment {idx + 1}:\n{fragment}"
            for idx, fragment in enumerate(context_fragments)
        )

        return HumanMessage(content=f"[CONTEXT]\n\n{context_content}\n\n[END OF CONTEXT]")

    @staticmethod
    def _build_history_messages(history_messages: Optional[List[Message]]) -> List[BaseMessage]:
        if not history_messages:
            return []

        messages: List[BaseMessage] = []

        for idx, message in enumerate(history_messages):
            try:
                if message.role == MessageRole.human:
                    messages.append(HumanMessage(content=message.content))
                elif message.role == MessageRole.assistant:
                    messages.append(AIMessage(content=message.content))
                else:
                    logger.warning(
                        "Unknown message role — skipping history message",
                        extra={"index": idx, "role": message.role}
                    )
            except Exception as e:
                logger.error(
                    "Failed to convert history message — skipping",
                    extra={
                        "index": idx,
                        "role": getattr(message, "role", "unknown"),
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    },
                    exc_info=True
                )

        logger.debug("History messages built", extra={"built_count": len(messages)})
        return messages

    @staticmethod
    def _build_question_message(question: str) -> HumanMessage:
        return HumanMessage(
            content=(
                "Based EXCLUSIVELY on the context provided above, "
                "answer the following question:\n\n"
                f"{question}"
            )
        )
