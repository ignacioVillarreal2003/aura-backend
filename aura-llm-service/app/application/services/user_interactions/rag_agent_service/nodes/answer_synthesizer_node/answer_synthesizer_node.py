import asyncio
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.user_interactions.rag_agent_service.interfaces.rag_node_interface import RagNodeInterface
from app.application.services.user_interactions.rag_agent_service.rag_agent_settings import AnswerSynthesizerSettings
from app.application.services.user_interactions.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState
from app.application.services.generation_shared.prompts.prompt_augmentation import augment_system_prompt
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_NO_ANSWER_RESPONSE = (
    "No se pudo generar una respuesta basada en la documentación disponible. "
    "Por favor, reformule su consulta o contacte a la unidad responsable."
)


class AnswerSynthesizerNode(RagNodeInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            settings: AnswerSynthesizerSettings,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._settings = settings
        self._llm: Optional[Runnable] = None
        self._llm_lock = asyncio.Lock()
        logger.debug("AnswerSynthesizerNode initialized")

    async def process(self, state: RagAgentState) -> Dict[str, Any]:
        logger.debug("Processing answer synthesizer")

        query: str = state.get("query", "")
        context: str = state.get("context", "")
        graph_facts: str = state.get("graph_facts", "")

        if not query or (not context and not graph_facts):
            logger.info("Missing query or context — returning fallback answer")
            return {"answer": _NO_ANSWER_RESPONSE}

        try:
            await self._ensure_llm_initialized()
            answer = await self._synthesize(
                query,
                context,
                state.get("operator_system_prompt"),
                state.get("response_style"),
                graph_facts,
            )

            if not answer:
                return {"answer": _NO_ANSWER_RESPONSE}

            logger.info("Answer synthesized", extra={"answer_length": len(answer)})
            return {"answer": answer}
        except Exception:
            logger.error("Answer synthesis failed — returning fallback", exc_info=True)
            return {"answer": _NO_ANSWER_RESPONSE}

    async def _synthesize(
            self,
            query: str,
            context: str,
            operator_system_prompt: Optional[str] = None,
            response_style: Optional[str] = None,
            graph_facts: str = "",
    ) -> str:
        sections = [f"Consulta: {query}"]
        if context:
            sections.append(f"Contexto documental:\n{context}")
        if graph_facts:
            sections.append(
                "Hechos del grafo de conocimiento (relaciones entre entidades "
                "extraídas de los documentos; cada hecho indica sus documentos fuente):\n"
                f"{graph_facts}"
            )
        sections.append("Sintetiza la respuesta final.")
        user_content = "\n\n".join(sections)
        prompt: List = [
            SystemMessage(
                content=augment_system_prompt(
                    self._settings.system_prompt,
                    operator_system_prompt,
                    response_style,
                )
            ),
            HumanMessage(content=user_content),
        ]
        return (await self._ollama_llm_invoker.call_llm_content(llm=self._llm, llm_input=prompt)).strip()

    async def _ensure_llm_initialized(self) -> None:
        if self._llm is not None:
            return
        async with self._llm_lock:
            if self._llm is not None:
                return
            self._llm = await self._ollama_llm_facade.get_llm_base()
            logger.debug("LLM initialized for answer synthesizer")
