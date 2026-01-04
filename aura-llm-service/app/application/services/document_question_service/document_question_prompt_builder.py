import logging
from typing import List
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage

from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)


class DocumentQuestionPromptBuilder:
    @staticmethod
    def build_system_message(system_prompt: str) -> SystemMessage:
        return SystemMessage(content=system_prompt)

    @staticmethod
    def build_context_message(fragments: List[str]) -> HumanMessage:
        if not fragments:
            logger.info("No context fragments provided, using empty context message")
            return HumanMessage(
                content="[CONTEXTO]: No se encontró información relevante en los documentos."
            )

        context_text = "\n\n---\n\n".join(
            f"Fragmento {idx + 1}:\n{fragment}"
            for idx, fragment in enumerate(fragments)
        )

        logger.debug(
            "Built context message",
            extra={
                "fragments_count": len(fragments),
                "total_length": len(context_text)
            }
        )

        return HumanMessage(
            content=(
                f"[CONTEXTO RELEVANTE DE DOCUMENTOS]\n\n"
                f"{context_text}\n\n"
                f"[FIN DEL CONTEXTO]"
            )
        )

    @staticmethod
    def build_history_messages(messages: List[Message]) -> List[BaseMessage]:
        if not messages:
            return []

        history: List[BaseMessage] = []

        for idx, message in enumerate(messages):
            try:
                if message.role == MessageRole.human:
                    history.append(HumanMessage(content=message.content))
                elif message.role == MessageRole.assistant:
                    history.append(AIMessage(content=message.content))
                else:
                    logger.warning(
                        "Skipping message with unknown role",
                        extra={
                            "index": idx,
                            "role": str(message.role)
                        }
                    )
            except Exception as e:
                logger.error(
                    "Error processing history message, skipping",
                    extra={
                        "index": idx,
                        "error": str(e)
                    }
                )
                continue

        logger.debug(
            "Built history messages",
            extra={
                "input_count": len(messages),
                "output_count": len(history)
            }
        )

        return history

    @staticmethod
    def build_question_message(question: str) -> HumanMessage:
        return HumanMessage(
            content=(
                f"Basándote EXCLUSIVAMENTE en el contexto proporcionado arriba, "
                f"responde la siguiente pregunta:\n\n{question}"
            )
        )

    @staticmethod
    def build_complete_prompt(system_prompt: str,
            fragments: List[str],
            messages: List[Message],
            question: str) -> List[BaseMessage]:
        prompt_messages: List[BaseMessage] = []

        prompt_messages.append(
            DocumentQuestionPromptBuilder.build_system_message(system_prompt)
        )

        prompt_messages.append(
            DocumentQuestionPromptBuilder.build_context_message(fragments)
        )

        prompt_messages.extend(
            DocumentQuestionPromptBuilder.build_history_messages(messages)
        )

        prompt_messages.append(
            DocumentQuestionPromptBuilder.build_question_message(question)
        )

        logger.info(
            "Complete prompt built",
            extra={
                "total_messages": len(prompt_messages),
                "fragments_count": len(fragments),
                "history_count": len(messages)
            }
        )

        return prompt_messages