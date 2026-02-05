import logging
from typing import List, Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage

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

        logger.info(
            "Starting complete prompt build",
            extra={
                "system_prompt": system_prompt,
                "question": question,
                "context_fragments": context_fragments,
                "history_messages": history_messages
            }
        )

        prompt_messages: List[BaseMessage] = []

        system_message = self._build_system_message(system_prompt)
        prompt_messages.append(system_message)

        context_message = self._build_context_message(context_fragments)
        prompt_messages.append(context_message)

        history_built = self._build_history_messages(history_messages)
        prompt_messages.extend(history_built)

        question_message = self._build_question_message(question)
        prompt_messages.append(question_message)

        logger.info("Complete prompt built successfully")

        return prompt_messages

    @staticmethod
    def _build_system_message(
            system_prompt: str
    ) -> SystemMessage:
        logger.debug(
            "Building system message",
            extra={
                "system_prompt": system_prompt
            }
        )

        return SystemMessage(
            content=system_prompt
        )

    @staticmethod
    def _build_context_message(
            context_fragments: Optional[List[str]]
    ) -> HumanMessage:
        logger.debug(
            "Building context message",
            extra={
                "context_fragments": context_fragments
            }
        )

        if not context_fragments:
            logger.info("No context fragments provided, using empty context message")
            return HumanMessage(
                content="[CONTEXTO]: No se encontró información relevante en los documentos."
            )

        context_content = "\n\n---\n\n".join(
            f"Fragmento de contexto {idx + 1}:\n{fragment}"
            for idx, fragment in enumerate(context_fragments)
        )

        logger.debug(
            "Context message built",
            extra={
                "context_content": context_content
            }
        )

        return HumanMessage(
            content=f"[CONTEXTO]\n\n{context_content}\n\n[FIN DEL CONTEXTO]"
        )

    @staticmethod
    def _build_history_messages(
            history_messages: Optional[List[Message]]
    ) -> List[BaseMessage]:
        logger.debug(
            "Building history messages",
            extra={
                "history_messages": history_messages
            }
        )

        if not history_messages:
            logger.info("No history messages provided")
            return []

        messages: List[BaseMessage] = []

        for idx, message in enumerate(history_messages):
            try:
                logger.debug(
                    "Processing history message",
                    extra={
                        "index": idx,
                        "role": message.role,
                        "content": message.content
                    }
                )

                if message.role == MessageRole.human:
                    messages.append(HumanMessage(content=message.content))

                elif message.role == MessageRole.assistant:
                    messages.append(AIMessage(content=message.content))

                else:
                    logger.warning(
                        "Unknown message role, skipping history message",
                        extra={
                            "index": idx,
                            "role": message.role,
                            "content": message.content
                        }
                    )

            except Exception as e:
                logger.error(
                    "Failed to convert history message, skipping",
                    extra={
                        "index": idx,
                        "role": getattr(message, "role", "unknown"),
                        "content_type": type(getattr(message, "content", None)).__name__,
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    },
                    exc_info=True
                )

        logger.info(
            "History messages build completed",
            extra={
                "messages": messages
            }
        )

        return messages

    @staticmethod
    def _build_question_message(
            question: str
    ) -> HumanMessage:
        logger.debug(
            "Building question message",
            extra={
                "question": question
            }
        )
        return HumanMessage(
            content=(
                "Basándote EXCLUSIVAMENTE en el contexto proporcionado arriba, "
                "responde la siguiente pregunta:\n\n"
                f"{question}"
            )
        )
