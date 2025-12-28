import logging
from typing import List
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage, AIMessage

from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)


class DocumentQuestionPromptBuilder:
    @staticmethod
    def build_system_prompt(system_prompt: str) -> SystemMessage:
        logger.debug("Building system prompt")

        return SystemMessage(
            content=system_prompt
        )

    @staticmethod
    def build_context_prompt(fragments: List[str]) -> HumanMessage:
        logger.debug("Building context prompt")

        if not fragments:
            logger.info("No context fragments provided")

            return HumanMessage(
                content="No se encontró contexto relevante en los documentos."
            )

        fragments_joined = "\n\n---\n\n".join(fragments)

        logger.debug("Context fragments joined")

        return HumanMessage(
            content=f"Contexto relevante extraído de documentos:\n\n{fragments_joined}"
        )

    @staticmethod
    def build_history_prompt(messages: List[Message]) -> List[BaseMessage]:
        logger.debug("Building history prompt")

        history: List[BaseMessage] = []

        for idx, message in enumerate(messages):
            if message.role == MessageRole.human:
                logger.debug(
                    "Adding human message to history",
                    extra={
                        "content": message.content
                    }
                )

                history.append(
                    HumanMessage(
                        content=message.content
                    )
                )

            elif message.role == MessageRole.assistant:
                logger.debug(
                    "Adding assistant message to history",
                    extra={
                        "content": message.content
                    }
                )

                history.append(
                    AIMessage(
                        content=message.content
                    )
                )

            else:
                logger.warning(
                    "Unknown message role in history",
                    extra={
                        "role": str(message.role),
                        "content": message.content
                    }
                )

        logger.debug("History prompt built")

        return history

    @staticmethod
    def build_question_prompt(question: str) -> HumanMessage:
        logger.debug("Building question prompt")

        return HumanMessage(
            content=f"Basado en el contexto proporcionado, responde a la siguiente pregunta:\n{question}"
        )

    @staticmethod
    def build_complete_prompt(system_prompt: str,
                              fragments: Sequence[str],
                              messages: List[Message],
                              question: str) -> List[BaseMessage]:
        logger.info(
            "Building complete LLM prompt",
            extra={
                "fragments": fragments,
                "messages": messages,
                "question": question
            }
        )

        llm_prompt: List[BaseMessage] = []

        llm_prompt.append(
            DocumentQuestionPromptBuilder.build_system_prompt(system_prompt)
        )
        llm_prompt.append(
            DocumentQuestionPromptBuilder.build_context_prompt(fragments)
        )
        llm_prompt.extend(
            DocumentQuestionPromptBuilder.build_history_prompt(messages)
        )
        llm_prompt.append(
            DocumentQuestionPromptBuilder.build_question_prompt(question)
        )

        logger.info("Complete LLM prompt built successfully")

        return llm_prompt
