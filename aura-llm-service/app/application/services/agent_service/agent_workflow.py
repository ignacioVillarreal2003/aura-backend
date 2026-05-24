import logging
from collections.abc import AsyncIterator
from typing import Optional

from langgraph.graph import END, StateGraph

from app.application.services.agent_service.agent_settings import AgentServiceSettings
from app.application.services.agent_service.agent_state.agent_state import AgentState
from app.application.services.agent_service.constants.node_name import NodeName
from app.application.services.agent_service.constants.query_intent import QueryIntent
from app.application.services.agent_service.nodes.answer_generator_node.answer_generator_node import AnswerGeneratorNode
from app.application.services.agent_service.nodes.context_builder_node.context_builder_node import ContextBuilderNode
from app.application.services.agent_service.nodes.context_resolver_node.context_resolver_node import ContextResolverNode
from app.application.services.agent_service.nodes.document_fetcher_node.document_fetcher_node import DocumentFetcherNode
from app.application.services.agent_service.nodes.fallback_node.fallback_node import FallbackNode
from app.application.services.agent_service.nodes.guardrails_node.guardrails_node import GuardrailsNode
from app.application.services.agent_service.nodes.input_normalizer_node.input_normalizer_node import InputNormalizerNode
from app.application.services.agent_service.nodes.intent_classifier_node.intent_classifier_node import IntentClassifierNode
from app.application.services.agent_service.nodes.keyword_extractor_node.keyword_extractor_node import KeywordExtractorNode
from app.application.services.agent_service.nodes.retriever_node.retriever_node import RetrieverNode
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)


# ── Routing functions ─────────────────────────────────────────────────────────

def _route_after_keyword_extractor(state: AgentState) -> str:
    intent = state.get("intent", "")
    if intent == QueryIntent.busqueda_documento.value:
        return NodeName.document_fetcher.value
    return NodeName.retriever.value


def _route_after_retrieval(state: AgentState) -> str:
    fragments = state.get("retrieved_fragments", [])
    return NodeName.context_builder.value if fragments else NodeName.fallback.value


def _route_after_guardrails(state: AgentState) -> str:
    return END if state.get("guardrail_passed", True) else NodeName.fallback.value


# ── Workflow ──────────────────────────────────────────────────────────────────

class AgentWorkflow:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            document_context_provider: DocumentContextProviderInterface,
            agent_service_settings: AgentServiceSettings,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._document_context_provider = document_context_provider
        self._agent_service_settings = agent_service_settings

        self._graph = StateGraph(AgentState)
        self._compiled_workflow = None

        self._input_normalizer_node: Optional[InputNormalizerNode] = None
        self._context_resolver_node: Optional[ContextResolverNode] = None
        self._intent_classifier_node: Optional[IntentClassifierNode] = None
        self._keyword_extractor_node: Optional[KeywordExtractorNode] = None
        self._retriever_node: Optional[RetrieverNode] = None
        self._document_fetcher_node: Optional[DocumentFetcherNode] = None
        self._context_builder_node: Optional[ContextBuilderNode] = None
        self._answer_generator_node: Optional[AnswerGeneratorNode] = None
        self._guardrails_node: Optional[GuardrailsNode] = None
        self._fallback_node: Optional[FallbackNode] = None

        logger.debug("AgentWorkflow initialized")

    async def build(self) -> None:
        logger.info("Building agent workflow")
        try:
            self._add_nodes()
            self._add_edges()
            self._compiled_workflow = self._graph.compile()
            logger.info("Agent workflow built successfully")
        except Exception as e:
            logger.exception("Failed to build agent workflow")
            raise RuntimeError("Failed to build agent workflow") from e

    async def invoke(self, state: AgentState) -> AgentState:
        if self._compiled_workflow is None:
            raise RuntimeError("Workflow not built. Call build() first.")
        return await self._compiled_workflow.ainvoke(state)

    async def stream(self, state: AgentState) -> AsyncIterator[tuple]:
        if self._compiled_workflow is None:
            raise RuntimeError("Workflow not built. Call build() first.")

        try:
            yield ("progress", NodeName.input_normalizer.value)
            delta = await self._input_normalizer_node.process(state)
            state = {**state, **delta}

            yield ("progress", NodeName.context_resolver.value)
            delta = await self._context_resolver_node.process(state)
            state = {**state, **delta}

            yield ("progress", NodeName.intent_classifier.value)
            delta = await self._intent_classifier_node.process(state)
            state = {**state, **delta}

            yield ("progress", NodeName.keyword_extractor.value)
            delta = await self._keyword_extractor_node.process(state)
            state = {**state, **delta}

            intent = state.get("intent", "")
            if intent == QueryIntent.busqueda_documento.value:
                yield ("progress", NodeName.document_fetcher.value)
                delta = await self._document_fetcher_node.process(state)
            else:
                yield ("progress", NodeName.retriever.value)
                delta = await self._retriever_node.process(state)
            state = {**state, **delta}

            if not state.get("retrieved_fragments"):
                yield ("progress", NodeName.fallback.value)
                delta = await self._fallback_node.process(state)
                state = {**state, **delta}
                yield ("done", state)
                return

            yield ("progress", NodeName.context_builder.value)
            delta = await self._context_builder_node.process(state)
            state = {**state, **delta}

            yield ("progress", NodeName.answer_generator.value)
            delta = await self._answer_generator_node.process(state)
            state = {**state, **delta}

            yield ("progress", NodeName.guardrails.value)
            delta = await self._guardrails_node.process(state)
            state = {**state, **delta}

            if not state.get("guardrail_passed", True):
                yield ("progress", NodeName.fallback.value)
                delta = await self._fallback_node.process(state)
                state = {**state, **delta}

            yield ("done", state)

        except Exception as e:
            logger.exception("Error during streaming agent workflow")
            yield ("error", e)

    def _add_nodes(self) -> None:
        logger.debug("Adding nodes to workflow graph")

        s = self._agent_service_settings

        self._input_normalizer_node = InputNormalizerNode()
        self._context_resolver_node = ContextResolverNode(
            ollama_llm_facade=self._ollama_llm_facade,
            settings=s.context_resolver,
        )
        self._intent_classifier_node = IntentClassifierNode(
            ollama_llm_facade=self._ollama_llm_facade,
            settings=s.intent_classifier,
        )
        self._keyword_extractor_node = KeywordExtractorNode(
            ollama_llm_facade=self._ollama_llm_facade,
            settings=s.keyword_extractor,
        )
        self._retriever_node = RetrieverNode(
            document_context_provider=self._document_context_provider,
            settings=s,
        )
        self._document_fetcher_node = DocumentFetcherNode(
            document_context_provider=self._document_context_provider,
            settings=s,
        )
        self._context_builder_node = ContextBuilderNode(settings=s)
        self._answer_generator_node = AnswerGeneratorNode(
            ollama_llm_facade=self._ollama_llm_facade,
            settings=s.answer_generator,
        )
        self._guardrails_node = GuardrailsNode(
            ollama_llm_facade=self._ollama_llm_facade,
            settings=s.guardrails,
        )
        self._fallback_node = FallbackNode()

        self._graph.add_node(NodeName.input_normalizer.value, self._input_normalizer_node.process)
        self._graph.add_node(NodeName.context_resolver.value, self._context_resolver_node.process)
        self._graph.add_node(NodeName.intent_classifier.value, self._intent_classifier_node.process)
        self._graph.add_node(NodeName.keyword_extractor.value, self._keyword_extractor_node.process)
        self._graph.add_node(NodeName.retriever.value, self._retriever_node.process)
        self._graph.add_node(NodeName.document_fetcher.value, self._document_fetcher_node.process)
        self._graph.add_node(NodeName.context_builder.value, self._context_builder_node.process)
        self._graph.add_node(NodeName.answer_generator.value, self._answer_generator_node.process)
        self._graph.add_node(NodeName.guardrails.value, self._guardrails_node.process)
        self._graph.add_node(NodeName.fallback.value, self._fallback_node.process)

    def _add_edges(self) -> None:
        logger.debug("Adding edges to workflow graph")

        self._graph.set_entry_point(NodeName.input_normalizer.value)

        # Linear pre-processing pipeline
        self._graph.add_edge(NodeName.input_normalizer.value, NodeName.context_resolver.value)
        self._graph.add_edge(NodeName.context_resolver.value, NodeName.intent_classifier.value)
        self._graph.add_edge(NodeName.intent_classifier.value, NodeName.keyword_extractor.value)

        # Branch: busqueda_documento → document_fetcher, else → retriever
        self._graph.add_conditional_edges(
            NodeName.keyword_extractor.value,
            _route_after_keyword_extractor,
            {
                NodeName.retriever.value: NodeName.retriever.value,
                NodeName.document_fetcher.value: NodeName.document_fetcher.value,
            },
        )

        # Both retrieval branches merge at context_builder (or fallback if empty)
        for retrieval_node in (NodeName.retriever.value, NodeName.document_fetcher.value):
            self._graph.add_conditional_edges(
                retrieval_node,
                _route_after_retrieval,
                {
                    NodeName.context_builder.value: NodeName.context_builder.value,
                    NodeName.fallback.value: NodeName.fallback.value,
                },
            )

        # Linear post-processing pipeline
        self._graph.add_edge(NodeName.context_builder.value, NodeName.answer_generator.value)
        self._graph.add_edge(NodeName.answer_generator.value, NodeName.guardrails.value)

        self._graph.add_conditional_edges(
            NodeName.guardrails.value,
            _route_after_guardrails,
            {END: END, NodeName.fallback.value: NodeName.fallback.value},
        )

        self._graph.add_edge(NodeName.fallback.value, END)
