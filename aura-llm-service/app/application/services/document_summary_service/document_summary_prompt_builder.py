import logging
from typing import List, Optional, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


class DocumentSummaryPromptBuilder:
    def build_summarization_messages(
            self,
            system_prompt: str,
            fragments: Optional[Sequence[str]],
    ) -> List[BaseMessage]:
        if not fragments:
            logger.debug("No fragments provided — using empty context message")
            return [
                self._build_system_message(system_prompt),
                HumanMessage(
                    content="[CONTEXTO]: No se encontró información relevante en el documento para generar un resumen."
                )
            ]

        fragments_joined = "\n\n---\n\n".join(
            f"Fragmento de contexto {idx + 1}:\n{fragment}"
            for idx, fragment in enumerate(fragments)
        )

        prompt = (
            "Analiza el siguiente contenido del documento y genera un resumen completo, estructurado y claro "
            "que capture los puntos principales y la información más importante.\n\n"
            f"Contenido del documento:\n\n{fragments_joined}\n\n"
            "Resumen:"
        )

        logger.debug(
            "Summarization messages built",
            extra={"fragment_count": len(fragments)}
        )

        return [
            self._build_system_message(system_prompt),
            HumanMessage(content=prompt)
        ]

    def build_reduction_messages(
            self,
            system_prompt: str,
            partial_summaries: Optional[Sequence[str]],
    ) -> List[BaseMessage]:
        if not partial_summaries:
            logger.debug("No partial summaries provided — using empty reduction message")
            return [
                self._build_system_message(system_prompt),
                HumanMessage(
                    content="[CONTEXTO]: No se recibieron resúmenes parciales para reducir/combinar."
                )
            ]

        joined_summaries = "\n\n---\n\n".join(
            f"Resumen parcial {idx + 1}:\n{summary}"
            for idx, summary in enumerate(partial_summaries)
        )

        prompt = (
            "A continuación se presentan múltiples resúmenes parciales de un documento más largo. "
            "Combínalos todos en un único resumen final que sea coherente, conciso y sin repeticiones. "
            "Preserva la estructura y los puntos principales de cada sección.\n\n"
            f"Resúmenes parciales:\n\n{joined_summaries}\n\n"
            "Resumen final:"
        )

        logger.debug(
            "Reduction messages built",
            extra={"partial_summary_count": len(partial_summaries)}
        )

        return [
            self._build_system_message(system_prompt),
            HumanMessage(content=prompt)
        ]

    @staticmethod
    def _build_system_message(system_prompt: str) -> SystemMessage:
        return SystemMessage(content=system_prompt)
