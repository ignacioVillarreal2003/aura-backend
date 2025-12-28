from typing import Sequence, List
from langchain_core.messages import SystemMessage, BaseMessage, HumanMessage


class DocumentSummaryMessageBuilder:
    @staticmethod
    def build_system_message(system_prompt: str) -> SystemMessage:
        return SystemMessage(content=system_prompt)

    @staticmethod
    def build_summarization_input(system_prompt: str,
                                  fragments: Sequence[str]) -> List[BaseMessage]:
        fragments_joined = "\n\n---\n\n".join(fragments)

        prompt = (
            "Analiza el siguiente contenido de un documento y genera un resumen completo, "
            "estructurado y claro que capture los puntos principales y la información más importante.\n\n"
            f"Contenido del documento:\n\n{fragments_joined}\n\n"
            "Resumen:"
        )

        return [
            DocumentSummaryMessageBuilder.build_system_message(system_prompt),
            HumanMessage(content=prompt)
        ]

    @staticmethod
    def build_reduction_input(system_prompt: str,
                              partial_summaries: List[str]) -> List[BaseMessage]:
        joined_summaries = "\n\n---\n\n".join(partial_summaries)

        prompt = (
            "A continuación tienes múltiples resúmenes parciales de un documento más grande. "
            "Fusiona todos en un único resumen final, coherente, conciso y sin repeticiones. "
            "Mantén la estructura y los puntos principales de cada sección.\n\n"
            f"Resúmenes parciales:\n\n{joined_summaries}\n\n"
            "Resumen final:"
        )

        return [
            DocumentSummaryMessageBuilder.build_system_message(system_prompt),
            HumanMessage(content=prompt)
        ]
