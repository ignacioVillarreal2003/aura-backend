import logging
from collections.abc import AsyncIterator
from typing import Awaitable, Callable, Optional
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph

from app.application.services.user_interactions.rag_agent_service.constants.rag_node_name import RagNodeName
from app.application.services.user_interactions.rag_agent_service.constants.rag_query_intent import RagQueryIntent
from app.application.services.user_interactions.rag_agent_service.nodes.answer_synthesizer_node.answer_synthesizer_node import (
    AnswerSynthesizerNode,
)
from app.application.services.user_interactions.rag_agent_service.nodes.context_grader_node.context_grader_node import (
    ContextGraderNode,
)
from app.application.services.user_interactions.rag_agent_service.nodes.context_retriever_node.context_retriever_node import (
    ContextRetrieverNode,
)
from app.application.services.user_interactions.rag_agent_service.nodes.document_fetcher_node.document_fetcher_node import (
    DocumentFetcherNode,
)
from app.application.services.user_interactions.rag_agent_service.nodes.query_refiner_node.query_refiner_node import (
    QueryRefinerNode,
)
from app.application.services.user_interactions.rag_agent_service.nodes.fallback_node.fallback_node import FallbackNode
from app.application.services.user_interactions.rag_agent_service.nodes.graph_context_retriever_node.graph_context_retriever_node import (
    GraphContextRetrieverNode,
)
from app.application.services.user_interactions.rag_agent_service.nodes.guardrails_node.guardrails_node import (
    GuardrailsNode,
)
from app.application.services.user_interactions.rag_agent_service.nodes.query_analyzer_node.query_analyzer_node import (
    QueryAnalyzerNode,
)
from app.application.services.user_interactions.rag_agent_service.rag_agent_settings import RagAgentServiceSettings
from app.application.services.user_interactions.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState
from app.configuration.tracing import generation_span
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.http.graph_context_provider.interfaces.graph_context_provider_interface import (
    GraphContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


_NODE_NAMES: frozenset[str] = frozenset(node.value for node in RagNodeName)

_NodeFn = Callable[[RagAgentState], Awaitable[dict]]


def _with_progress(node_name: str, fn: _NodeFn) -> _NodeFn:
    async def _runner(state: RagAgentState) -> dict:
        with generation_span(f"rag_agent.{node_name}"):
            try:
                writer = get_stream_writer()
                if writer is not None:
                    writer({"progress_node": node_name})
            except Exception:
                pass
            return await fn(state)

    return _runner


def _retrieve_context_enabled(state: RagAgentState) -> bool:
    """¿Corre la recuperación RAG/grafo del knowledge base?

    Tri-estado: si el operador fijó el flag se respeta; si viene en None se usa el
    default del agente (recuperar salvo que el intent sea pedir un documento entero).
    """
    flag = state.get("retrieve_context")
    if flag is not None:
        return flag
    return state.get("intent") != RagQueryIntent.document_lookup.value


def _process_documents_enabled(state: RagAgentState) -> bool:
    """¿Corre la traída del contenido completo de los documentos más relevantes?

    Tri-estado: respeta el flag del operador; en None usa el default del agente
    (traer documentos completos solo cuando el intent es un pedido de documento).
    """
    flag = state.get("process_documents")
    if flag is not None:
        return flag
    return state.get("intent") == RagQueryIntent.document_lookup.value


def _select_retrieval(state: RagAgentState) -> str:
    """Primer nodo de recuperación a ejecutar según los flags (o el default por intent).

    Si ambos están activos, se entra por `context_retriever` y luego se encadena al
    `document_fetcher` (los fragmentos se mergean). Si ninguno aplica, se salta
    directo a la síntesis.
    """
    if _retrieve_context_enabled(state):
        return RagNodeName.context_retriever.value
    if _process_documents_enabled(state):
        return RagNodeName.document_fetcher.value
    return RagNodeName.answer_synthesizer.value


def _route_after_context_retriever_grader(state: RagAgentState) -> str:
    if _process_documents_enabled(state):
        return RagNodeName.document_fetcher.value
    return RagNodeName.context_grader.value


def _route_after_context_retriever_plain(state: RagAgentState) -> str:
    if _process_documents_enabled(state):
        return RagNodeName.document_fetcher.value
    return _route_after_retrieval(state)


def _route_after_retrieval(state: RagAgentState) -> str:
    if state.get("retrieved_fragments") or state.get("graph_facts"):
        return RagNodeName.answer_synthesizer.value
    return RagNodeName.fallback.value


def _route_after_grader(state: RagAgentState) -> str:
    if state.get("context_sufficient", True):
        return RagNodeName.answer_synthesizer.value
    if state.get("can_retry", False):
        return RagNodeName.query_refiner.value
    if state.get("retrieved_fragments") or state.get("graph_facts"):
        return RagNodeName.answer_synthesizer.value
    return RagNodeName.fallback.value


def _route_after_guardrails(state: RagAgentState) -> str:
    return END if state.get("guardrail_passed", True) else RagNodeName.fallback.value


class RagAgentWorkflow:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            settings: RagAgentServiceSettings,
            graph_context_provider: Optional[GraphContextProviderInterface] = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._document_context_provider = document_context_provider
        self._graph_context_provider = graph_context_provider
        self._settings = settings

        self._graph = StateGraph(RagAgentState)
        self._compiled_workflow = None

        self._query_analyzer_node: Optional[QueryAnalyzerNode] = None
        self._graph_context_retriever_node: Optional[GraphContextRetrieverNode] = None
        self._context_retriever_node: Optional[ContextRetrieverNode] = None
        self._document_fetcher_node: Optional[DocumentFetcherNode] = None
        self._context_grader_node: Optional[ContextGraderNode] = None
        self._query_refiner_node: Optional[QueryRefinerNode] = None
        self._answer_synthesizer_node: Optional[AnswerSynthesizerNode] = None
        self._guardrails_node: Optional[GuardrailsNode] = None
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

        final_state: RagAgentState = state
        try:
            async for mode, chunk in self._compiled_workflow.astream(
                    state, stream_mode=["custom", "values"]
            ):
                if mode == "custom":
                    if isinstance(chunk, dict):
                        node_name = chunk.get("progress_node")
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
            ollama_llm_invoker=self._ollama_llm_invoker,
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
        self._document_fetcher_node = DocumentFetcherNode(
            document_context_provider=self._document_context_provider,
            settings=s,
        )
        self._context_grader_node = ContextGraderNode(
            ollama_llm_facade=self._ollama_llm_facade,
            ollama_llm_invoker=self._ollama_llm_invoker,
            settings=s.context_grader,
            max_retrieval_attempts=s.max_retrieval_attempts,
        )
        self._query_refiner_node = QueryRefinerNode(
            ollama_llm_facade=self._ollama_llm_facade,
            ollama_llm_invoker=self._ollama_llm_invoker,
            settings=s.query_refiner,
        )
        self._answer_synthesizer_node = AnswerSynthesizerNode(
            ollama_llm_facade=self._ollama_llm_facade,
            ollama_llm_invoker=self._ollama_llm_invoker,
            settings=s.answer_synthesizer,
        )
        self._guardrails_node = GuardrailsNode(
            ollama_llm_facade=self._ollama_llm_facade,
            ollama_llm_invoker=self._ollama_llm_invoker,
            settings=s.guardrails,
        )
        self._fallback_node = FallbackNode()

        def _add(name: str, fn: _NodeFn) -> None:
            self._graph.add_node(name, _with_progress(name, fn))

        _add(RagNodeName.query_analyzer.value, self._query_analyzer_node.process)
        _add(RagNodeName.graph_context_retriever.value, self._graph_context_retriever_node.process)
        _add(RagNodeName.context_retriever.value, self._context_retriever_node.process)
        _add(RagNodeName.document_fetcher.value, self._document_fetcher_node.process)
        if self._settings.use_context_grader:
            _add(RagNodeName.context_grader.value, self._context_grader_node.process)
            _add(RagNodeName.query_refiner.value, self._query_refiner_node.process)
        _add(RagNodeName.answer_synthesizer.value, self._answer_synthesizer_node.process)
        if self._settings.use_guardrails:
            _add(RagNodeName.guardrails.value, self._guardrails_node.process)
        _add(RagNodeName.fallback.value, self._fallback_node.process)

    def _add_edges(self) -> None:
        self._graph.set_entry_point(RagNodeName.query_analyzer.value)

        self._graph.add_edge(
            RagNodeName.query_analyzer.value,
            RagNodeName.graph_context_retriever.value,
        )

        # Entrada a la recuperación según los flags del operador (o el default por
        # intent). Si no aplica ninguno, se salta directo a la síntesis.
        self._graph.add_conditional_edges(
            RagNodeName.graph_context_retriever.value,
            _select_retrieval,
            {
                RagNodeName.context_retriever.value: RagNodeName.context_retriever.value,
                RagNodeName.document_fetcher.value: RagNodeName.document_fetcher.value,
                RagNodeName.answer_synthesizer.value: RagNodeName.answer_synthesizer.value,
            },
        )

        if self._settings.use_context_grader:
            # context_retriever encadena al document_fetcher si también se pidió
            # procesar documentos; si no, pasa al grader.
            self._graph.add_conditional_edges(
                RagNodeName.context_retriever.value,
                _route_after_context_retriever_grader,
                {
                    RagNodeName.document_fetcher.value: RagNodeName.document_fetcher.value,
                    RagNodeName.context_grader.value: RagNodeName.context_grader.value,
                },
            )
            self._graph.add_edge(RagNodeName.document_fetcher.value, RagNodeName.context_grader.value)
            self._graph.add_conditional_edges(
                RagNodeName.context_grader.value,
                _route_after_grader,
                {
                    RagNodeName.answer_synthesizer.value: RagNodeName.answer_synthesizer.value,
                    RagNodeName.query_refiner.value: RagNodeName.query_refiner.value,
                    RagNodeName.fallback.value: RagNodeName.fallback.value,
                },
            )
            # Tras refinar la consulta se re-entra a la recuperación honrando los flags.
            self._graph.add_conditional_edges(
                RagNodeName.query_refiner.value,
                _select_retrieval,
                {
                    RagNodeName.context_retriever.value: RagNodeName.context_retriever.value,
                    RagNodeName.document_fetcher.value: RagNodeName.document_fetcher.value,
                    RagNodeName.answer_synthesizer.value: RagNodeName.answer_synthesizer.value,
                },
            )
        else:
            # context_retriever → document_fetcher (si se pidió) o directo a síntesis/fallback.
            self._graph.add_conditional_edges(
                RagNodeName.context_retriever.value,
                _route_after_context_retriever_plain,
                {
                    RagNodeName.document_fetcher.value: RagNodeName.document_fetcher.value,
                    RagNodeName.answer_synthesizer.value: RagNodeName.answer_synthesizer.value,
                    RagNodeName.fallback.value: RagNodeName.fallback.value,
                },
            )
            self._graph.add_conditional_edges(
                RagNodeName.document_fetcher.value,
                _route_after_retrieval,
                {
                    RagNodeName.answer_synthesizer.value: RagNodeName.answer_synthesizer.value,
                    RagNodeName.fallback.value: RagNodeName.fallback.value,
                },
            )

        if self._settings.use_guardrails:
            self._graph.add_edge(RagNodeName.answer_synthesizer.value, RagNodeName.guardrails.value)
            self._graph.add_conditional_edges(
                RagNodeName.guardrails.value,
                _route_after_guardrails,
                {END: END, RagNodeName.fallback.value: RagNodeName.fallback.value},
            )
        else:
            self._graph.add_edge(RagNodeName.answer_synthesizer.value, END)

        self._graph.add_edge(RagNodeName.fallback.value, END)
