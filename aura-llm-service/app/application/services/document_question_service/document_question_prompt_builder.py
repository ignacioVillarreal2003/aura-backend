import logging
from typing import List
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage

from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)


class DocumentQuestionPromptBuilder:
    @staticmethod
    def build_system_prompt_message(system_prompt: str) -> SystemMessage:
        logger.debug(
            "Built system message",
            extra={
                "system_prompt": system_prompt
            }
        )
        return SystemMessage(content=system_prompt)

    @staticmethod
    def build_context_fragments_message(context_fragments: List[str]) -> HumanMessage:
        if not context_fragments:
            logger.info("No context fragments provided, using empty context message")
            return HumanMessage(
                content="[CONTEXTO]: No se encontró información relevante en los documentos."
            )

        context = "\n\n---\n\n".join(
            f"Fragmento de contexto {idx + 1}:\n{context_fragment}"
            for idx, context_fragment in enumerate(context_fragments)
        )

        logger.debug(
            "Built context fragments message",
            extra={
                "context_fragments": context_fragments
            }
        )

        return HumanMessage(
            content=(
                f"[CONTEXTO]\n\n"
                f"{context}\n\n"
                f"[FIN DEL CONTEXTO]"
            )
        )

    @staticmethod
    def build_history_messages_message(history_messages: List[Message]) -> List[BaseMessage]:
        if not history_messages:
            return []

        history: List[BaseMessage] = []

        for idx, history_message in enumerate(history_messages):
            try:
                if history_message.role == MessageRole.human:
                    history.append(HumanMessage(content=history_message.content))
                elif history_message.role == MessageRole.assistant:
                    history.append(AIMessage(content=history_message.content))
                else:
                    logger.warning(
                        "Skipping message with unknown role",
                        extra={
                            "index": idx,
                            "role": history_message.role
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
            "Built history messages message",
            extra={
                "history_messages": history_messages
            }
        )

        return history

    @staticmethod
    def build_question_message(question: str) -> HumanMessage:
        logger.debug(
            "Built question message",
            extra={
                "question": question
            }
        )
        return HumanMessage(
            content=(
                f"Basándote EXCLUSIVAMENTE en el contexto proporcionado arriba, "
                f"responde la siguiente pregunta:\n\n{question}"
            )
        )

    @staticmethod
    def build_complete_prompt(system_prompt: str,
                              context_fragments: List[str],
                              history_messages: List[Message],
                              question: str) -> List[BaseMessage]:
        prompt_messages: List[BaseMessage] = []

        prompt_messages.append(
            DocumentQuestionPromptBuilder.build_system_prompt_message(system_prompt)
        )

        prompt_messages.append(
            DocumentQuestionPromptBuilder.build_context_fragments_message(context_fragments)
        )

        prompt_messages.extend(
            DocumentQuestionPromptBuilder.build_history_messages_message(history_messages)
        )

        prompt_messages.append(
            DocumentQuestionPromptBuilder.build_question_message(question)
        )

        logger.info(
            "Complete prompt built",
            extra={
                "prompt_messages": prompt_messages
            }
        )

        return prompt_messages
