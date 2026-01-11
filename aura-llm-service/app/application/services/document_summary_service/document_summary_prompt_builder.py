import logging
from typing import Sequence, List, Optional
from langchain_core.messages import SystemMessage, BaseMessage, HumanMessage

logger = logging.getLogger(__name__)


class DocumentSummaryPromptBuilder:
    @staticmethod
    def _build_system_message(system_prompt: str) -> SystemMessage:
        logger.debug(
            "Building system message",
            extra={
                "system_prompt": system_prompt
            }
        )
        return SystemMessage(
            content=system_prompt
        )

    def build_summarization_messages(self,
                                     system_prompt: str,
                                     fragments: Optional[Sequence[str]]) -> List[BaseMessage]:
        logger.info(
            "Starting summarization messages build",
            extra={
                "system_prompt": system_prompt,
                "fragments": fragments
            }
        )

        if not fragments:
            logger.info("No fragments provided, using empty context message")
            return [
                self._build_system_message(system_prompt),
                HumanMessage(
                    content="[CONTEXTO]: No se encontró información relevante en el documento para generar un resumen."
                )
            ]

        try:
            fragments_joined = "\n\n---\n\n".join(
                f"Fragmento de contexto {idx + 1}:\n{fragment}"
                for idx, fragment in enumerate(fragments)
            )
            logger.debug(
                "Fragments joined for summarization",
                extra={
                    "fragments_joined": fragments_joined
                }
            )
        except Exception as e:
            logger.error(
                "Failed to join fragments for summarization",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            return [
                self._build_system_message(system_prompt),
                HumanMessage(content="[CONTEXTO]: Error procesando el contenido del documento.")
            ]

        prompt = (
            "Analiza el siguiente contenido de un documento y genera un resumen completo, "
            "estructurado y claro que capture los puntos principales y la información más importante.\n\n"
            f"Contenido del documento:\n\n{fragments_joined}\n\n"
            "Resumen:"
        )

        messages: List[BaseMessage] = [
            self._build_system_message(system_prompt),
            HumanMessage(content=prompt)
        ]

        logger.info(
            "Summarization messages built successfully",
            extra={
                "messages_count": len(messages),
                "fragments_count": len(fragments)
            }
        )

        return messages

    def build_reduction_messages(self,
                                 system_prompt: str,
                                 partial_summaries: Optional[Sequence[str]]) -> List[BaseMessage]:
        logger.info(
            "Starting reduction messages build",
            extra={
                "system_prompt": system_prompt,
                "partial_summaries": partial_summaries
            }
        )

        if not partial_summaries:
            logger.info("No partial summaries provided, using empty reduction message")
            return [
                self._build_system_message(system_prompt),
                HumanMessage(
                    content="[CONTEXTO]: No se recibieron resúmenes parciales para reducir/combinar."
                )
            ]

        try:
            joined_summaries = "\n\n---\n\n".join(
                f"Resumen parcial {idx + 1}:\n{summary}"
                for idx, summary in enumerate(partial_summaries)
            )
            logger.debug(
                "Partial summaries joined for reduction",
                extra={
                    "joined_summaries": joined_summaries
                }
            )
        except Exception as e:
            logger.error(
                "Failed to join partial summaries for reduction",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            return [
                self._build_system_message(system_prompt),
                HumanMessage(content="[CONTEXTO]: Error procesando los resúmenes parciales.")
            ]

        prompt = (
            "A continuación tienes múltiples resúmenes parciales de un documento más grande. "
            "Fusiona todos en un único resumen final, coherente, conciso y sin repeticiones. "
            "Mantén la estructura y los puntos principales de cada sección.\n\n"
            f"Resúmenes parciales:\n\n{joined_summaries}\n\n"
            "Resumen final:"
        )

        messages: List[BaseMessage] = [
            self._build_system_message(system_prompt),
            HumanMessage(content=prompt)
        ]

        logger.info(
            "Reduction messages built successfully",
            extra={
                "messages": messages
            }
        )

        return messages
