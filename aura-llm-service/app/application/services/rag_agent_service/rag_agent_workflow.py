import logging

from langgraph.graph import END, StateGraph

from app.application.services.rag_agent_service.constants.rag_node_name import RagNodeName
from app.application.services.rag_agent_service.nodes.answer_synthesizer_node.answer_synthesizer_node import (
    AnswerSynthesizerNode,
)
from app.application.services.rag_agent_service.nodes.context_evaluator_node.context_evaluator_node import (
    ContextEvaluatorNode,
)
from app.application.services.rag_agent_service.nodes.context_retriever_node.context_retriever_node import (
    ContextRetrieverNode,
)
from app.application.services.rag_agent_service.nodes.fallback_node.fallback_node import FallbackNode
from app.application.services.rag_agent_service.nodes.query_analyzer_node.query_analyzer_node import QueryAnalyzerNode
from app.application.services.rag_agent_service.nodes.reasoning_node.reasoning_node import ReasoningNode
from app.application.services.rag_agent_service.rag_agent_settings import RagAgentServiceSettings
from app.application.services.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)


def _route_after_context_evaluator(state: RagAgentState) -> str:
    if state.get("context_sufficient", False):
        return RagNodeName.reasoning.value
    return RagNodeName.fallback.value


class RagAgentWorkflow:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            document_context_provider: DocumentContextProviderInterface,
            settings: RagAgentServiceSettings,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._document_context_provider = document_context_provider
        self._settings = settings

        self._graph = StateGraph(RagAgentState)
        self._compiled_workflow = None

        logger.debug("RagAgentWorkflow initialized")

    async def build(self) -> None:
        logger.info("Building RAG agent workflow")
        try:
            self._add_nodes()
            self._add_edges()
            self._compiled_workflow = self._graph.compile()
            logger.info("RAG agent workflow built successfully")
        except Exception as e:
            logger.exception("Failed to build RAG agent workflow")
            raise RuntimeError("Failed to build RAG agent workflow") from e

    async def invoke(self, state: RagAgentState) -> RagAgentState:
        if self._compiled_workflow is None:
            raise RuntimeError("Workflow not built. Call build() first.")
        return await self._compiled_workflow.ainvoke(state)

    def _add_nodes(self) -> None:
        s = self._settings

        self._graph.add_node(
            RagNodeName.query_analyzer.value,
            QueryAnalyzerNode(
                ollama_llm_facade=self._ollama_llm_facade,
                settings=s.query_analyzer,
            ).process,
        )
        self._graph.add_node(
            RagNodeName.context_retriever.value,
            ContextRetrieverNode(
                document_context_provider=self._document_context_provider,
                settings=s,
            ).process,
        )
        self._graph.add_node(
            RagNodeName.context_evaluator.value,
            ContextEvaluatorNode(
                ollama_llm_facade=self._ollama_llm_facade,
                settings=s.context_evaluator,
            ).process,
        )
        self._graph.add_node(
            RagNodeName.reasoning.value,
            ReasoningNode(
                ollama_llm_facade=self._ollama_llm_facade,
                settings=s.reasoning,
            ).process,
        )
        self._graph.add_node(
            RagNodeName.answer_synthesizer.value,
            AnswerSynthesizerNode(
                ollama_llm_facade=self._ollama_llm_facade,
                settings=s.answer_synthesizer,
            ).process,
        )
        self._graph.add_node(
            RagNodeName.fallback.value,
            FallbackNode().process,
        )

    def _add_edges(self) -> None:
        self._graph.set_entry_point(RagNodeName.query_analyzer.value)

        self._graph.add_edge(RagNodeName.query_analyzer.value, RagNodeName.context_retriever.value)
        self._graph.add_edge(RagNodeName.context_retriever.value, RagNodeName.context_evaluator.value)

        self._graph.add_conditional_edges(
            RagNodeName.context_evaluator.value,
            _route_after_context_evaluator,
            {
                RagNodeName.reasoning.value: RagNodeName.reasoning.value,
                RagNodeName.fallback.value: RagNodeName.fallback.value,
            },
        )

        self._graph.add_edge(RagNodeName.reasoning.value, RagNodeName.answer_synthesizer.value)
        self._graph.add_edge(RagNodeName.answer_synthesizer.value, END)
        self._graph.add_edge(RagNodeName.fallback.value, END)
