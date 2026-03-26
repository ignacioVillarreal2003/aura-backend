import logging
from typing import Optional
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from app.application.services.agent_service.agent_configuration import AgentConfiguration
from app.application.services.agent_service.agent_node.agent_node import AgentNode
from app.application.services.agent_service.agent_node.agent_node_configuration import AgentNodeConfiguration
from app.application.services.agent_service.agent_state.agent_state import AgentState
from app.application.services.agent_service.constants.node_name import NodeName
from app.application.services.agent_service.sentiment_node.sentiment_node import SentimentNode
from app.application.services.agent_service.sentiment_node.sentiment_node_configuration import (
    SentimentNodeConfiguration
)
from app.application.services.agent_service.tools.tool_call_router import ToolCallRouter
from app.infrastructure.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)


class AgentWorkflow:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            agent_configuration: AgentConfiguration,
            sentiment_node_configuration: SentimentNodeConfiguration,
            agent_node_configuration: AgentNodeConfiguration
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._agent_configuration = agent_configuration
        self._sentiment_node_configuration = sentiment_node_configuration
        self._agent_node_configuration = agent_node_configuration

        self._workflow = StateGraph(AgentState)
        self._compiled_workflow = None

        self._sentiment_node: Optional[SentimentNode] = None
        self._agent_node: Optional[AgentNode] = None
        self._tool_node: Optional[ToolNode] = None

        logger.debug("AgentWorkflow initialized")

    async def build(self):
        logger.info("Building agent workflow")

        try:
            await self._create_nodes()
            self._add_nodes()
            self._set_entry_point()
            self._add_edges()
            self._compiled_workflow = self._workflow.compile()
            logger.info("Agent workflow built successfully")
            return self._compiled_workflow
        except Exception as e:
            logger.exception("Failed to build agent workflow")
            raise RuntimeError("Failed to build agent workflow") from e

    async def invoke(self, state: AgentState):
        if self._compiled_workflow is None:
            raise RuntimeError("Workflow not built. Call build() first.")
        return await self._compiled_workflow.ainvoke(state)

    async def _create_nodes(self) -> None:
        logger.debug("Creating workflow nodes")

        self._sentiment_node = SentimentNode(
            ollama_llm_facade=self._ollama_llm_facade,
            configuration=self._sentiment_node_configuration
        )

        self._agent_node = AgentNode(
            ollama_llm_facade=self._ollama_llm_facade,
            configuration=self._agent_node_configuration
        )

        tools = self._ollama_llm_facade.tools
        if tools:
            self._tool_node = ToolNode(tools)
            logger.debug("Tool node created", extra={"tool_count": len(tools)})

    def _add_nodes(self) -> None:
        logger.debug("Adding nodes to workflow graph")

        if self._sentiment_node is not None:
            self._workflow.add_node(NodeName.sentiment_node.value, self._sentiment_node.process)

        if self._agent_node is not None:
            self._workflow.add_node(NodeName.agent_node.value, self._agent_node.process)

        if self._tool_node is not None:
            self._workflow.add_node(NodeName.tools.value, self._tool_node)

    def _set_entry_point(self) -> None:
        entry_point = (
            NodeName.sentiment_node.value
            if self._sentiment_node
            else NodeName.agent_node.value
        )
        self._workflow.set_entry_point(entry_point)

    def _add_edges(self) -> None:
        if self._sentiment_node:
            self._workflow.add_edge(NodeName.sentiment_node.value, NodeName.agent_node.value)

        if self._tool_node:
            router = ToolCallRouter(
                max_iterations=self._agent_configuration.max_tool_iterations
            )
            self._workflow.add_conditional_edges(
                NodeName.agent_node.value,
                router.should_continue,
                {"tools": NodeName.tools.value, END: END}
            )
            self._workflow.add_edge(NodeName.tools.value, NodeName.agent_node.value)
        else:
            self._workflow.add_edge(NodeName.agent_node.value, END)
