import logging
from collections.abc import AsyncIterator
from typing import Optional
from langgraph.graph import END, StateGraph

from app.application.services.user_interactions.rag_agent_service.constants.rag_node_name import RagNodeName
from app.application.services.user_interactions.rag_agent_service.nodes.answer_synthesizer_node.answer_synthesizer_node import (
    AnswerSynthesizerNode,
)
from app.application.services.user_interactions.rag_agent_service.nodes.context_retriever_node.context_retriever_node import (
    ContextRetrieverNode,
)
from app.application.services.user_interactions.rag_agent_service.nodes.fallback_node.fallback_node import FallbackNode
from app.application.services.user_interactions.rag_agent_service.nodes.graph_context_retriever_node.graph_context_retriever_node import (
    GraphContextRetrieverNode,
)
from app.application.services.user_interactions.rag_agent_service.nodes.query_analyzer_node.query_analyzer_node import \
    QueryAnalyzerNode
from app.application.services.user_interactions.rag_agent_service.rag_agent_settings import RagAgentServiceSettings
from app.application.services.user_interactions.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.http.graph_context_provider.interfaces.graph_context_provider_interface import (
    GraphContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)


_NODE_NAMES: frozenset[str] = frozenset(node.value for node in RagNodeName)


def _route_after_context_retriever(state: RagAgentState) -> str:
    if state.get("retrieved_fragments") or state.get("graph_facts"):
        return RagNodeName.answer_synthesizer.value
    return RagNodeName.fallback.value


class RagAgentWorkflow:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            document_context_provider: DocumentContextProviderInterface,
            settings: RagAgentServiceSettings,
            graph_context_provider: Optional[GraphContextProviderInterface] = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._document_context_provider = document_context_provider
        self._graph_context_provider = graph_context_provider
        self._settings = settings

        self._graph = StateGraph(RagAgentState)
        self._compiled_workflow = None

        self._query_analyzer_node: Optional[QueryAnalyzerNode] = None
        self._graph_context_retriever_node: Optional[GraphContextRetrieverNode] = None
        self._context_retriever_node: Optional[ContextRetrieverNode] = None
        self._answer_synthesizer_node: Optional[AnswerSynthesizerNode] = None
        self._fallback_node: Optional[FallbackNode] = None

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

    async def stream(self, state: RagAgentState) -> AsyncIterator[tuple]:
        if self._compiled_workflow is None:
            raise RuntimeError("Workflow not built. Call build() first.")

        # Drive the compiled graph directly (single source of truth) rather than
        # replaying node routing by hand.
        final_state: RagAgentState = state
        try:
            async for mode, chunk in self._compiled_workflow.astream(
                    state, stream_mode=["updates", "values"]
            ):
                if mode == "updates":
                    if isinstance(chunk, dict):
                        for node_name in chunk:
                            if node_name in _NODE_NAMES:
                                yield ("progress", node_name)
                elif mode == "values":
                    final_state = chunk

            yield ("done", final_state)

        except Exception as e:
            logger.exception("Error during streaming RAG workflow")
            yield ("error", e)

    def _add_nodes(self) -> None:
        s = self._settings

        self._query_analyzer_node = QueryAnalyzerNode(
            ollama_llm_facade=self._ollama_llm_facade,
            settings=s.query_analyzer,
        )
        self._graph_context_retriever_node = GraphContextRetrieverNode(
            graph_context_provider=self._graph_context_provider,
            settings=s,
        )
        self._context_retriever_node = ContextRetrieverNode(
            document_context_provider=self._document_context_provider,
            settings=s,
        )
        self._answer_synthesizer_node = AnswerSynthesizerNode(
            ollama_llm_facade=self._ollama_llm_facade,
            settings=s.answer_synthesizer,
        )
        self._fallback_node = FallbackNode()

        self._graph.add_node(RagNodeName.query_analyzer.value, self._query_analyzer_node.process)
        self._graph.add_node(
            RagNodeName.graph_context_retriever.value,
            self._graph_context_retriever_node.process,
        )
        self._graph.add_node(RagNodeName.context_retriever.value, self._context_retriever_node.process)
        self._graph.add_node(RagNodeName.answer_synthesizer.value, self._answer_synthesizer_node.process)
        self._graph.add_node(RagNodeName.fallback.value, self._fallback_node.process)

    def _add_edges(self) -> None:
        self._graph.set_entry_point(RagNodeName.query_analyzer.value)

        self._graph.add_edge(
            RagNodeName.query_analyzer.value,
            RagNodeName.graph_context_retriever.value,
        )
        self._graph.add_edge(
            RagNodeName.graph_context_retriever.value,
            RagNodeName.context_retriever.value,
        )

        self._graph.add_conditional_edges(
            RagNodeName.context_retriever.value,
            _route_after_context_retriever,
            {
                RagNodeName.answer_synthesizer.value: RagNodeName.answer_synthesizer.value,
                RagNodeName.fallback.value: RagNodeName.fallback.value,
            },
        )

        self._graph.add_edge(RagNodeName.answer_synthesizer.value, END)
        self._graph.add_edge(RagNodeName.fallback.value, END)
