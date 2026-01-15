import logging
from typing import Optional
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from app.application.services.agent_service.agent_configuration import AgentConfiguration
from app.application.services.agent_service.agent_node_configuration import AgentNodeConfiguration
from app.application.services.agent_service.agent_workflow.tool_call_router import NodeName, ToolCallRouter
from app.application.services.agent_service.nodes.agent_node import AgentNode
from app.application.services.agent_service.nodes.sentiment_node import SentimentNode
from app.application.services.agent_service.sentiment_configuration import SentimentConfiguration
from app.application.services.agent_service.agent_state.agent_state import AgentState
from app.infrastructure.ollama_llm_facade.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)


class AgentWorkflowBuilder:
    def __init__(self,
                 ollama_llm_facade: OllamaLLMFacadeInterface,
                 agent_configuration: Optional[AgentConfiguration] = None,
                 sentiment_configuration: Optional[SentimentConfiguration] = None,
                 agent_node_configuration: Optional[AgentNodeConfiguration] = None) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._agent_configuration = agent_configuration or AgentConfiguration()
        self._sentiment_configuration = sentiment_configuration
        self._agent_node_configuration = agent_node_configuration

        self._workflow = StateGraph(AgentState)

        self._sentiment_node: Optional[SentimentNode] = None
        self._agent_node: Optional[AgentNode] = None
        self._tool_node: Optional[ToolNode] = None

        logger.debug("AgentWorkflowBuilder initialized")

    async def build(self):
        logger.info("Building agent workflow")

        try:
            await self._create_nodes()

            self._add_nodes()

            self._set_entry_point()

            self._add_edges()

            compiled = self._workflow.compile()

            logger.info("Agent workflow built successfully")

            return compiled

        except Exception as e:
            logger.exception("Failed to build agent workflow")
            raise RuntimeError("Failed to build agent workflow") from e

    async def _create_nodes(self) -> None:
        logger.debug("Creating workflow nodes")

        if self._agent_configuration.enable_sentiment_analysis:
            self._sentiment_node = SentimentNode(
                ollama_llm_facade=self._ollama_llm_facade,
                configuration=self._sentiment_configuration
            )
            logger.debug("Sentiment node created")

        self._agent_node = AgentNode(
            ollama_llm_facade=self._ollama_llm_facade,
            configuration=self._agent_node_configuration
        )
        logger.debug("Agent node created")

        tools = self._ollama_llm_facade.tools
        if tools:
            self._tool_node = ToolNode(tools)
            logger.debug(f"Tool node created with {len(tools)} tools")
        else:
            logger.debug("No tools available, tool node not created")

    def _add_nodes(self) -> None:
        logger.debug("Adding nodes to workflow graph")

        if self._sentiment_node:
            self._workflow.add_node(
                NodeName.SENTIMENT_ANALYZER.value,
                self._sentiment_node
            )
            logger.debug("Sentiment analyzer node added")

        if self._agent_node is None:
            raise RuntimeError("Agent node must be created before adding to workflow")

        self._workflow.add_node(
            NodeName.AGENT.value,
            self._agent_node
        )
        logger.debug("Agent node added")

        if self._tool_node:
            self._workflow.add_node(
                NodeName.TOOLS.value,
                self._tool_node
            )
            logger.debug("Tools node added")

    def _set_entry_point(self) -> None:
        if self._sentiment_node:
            entry_point = NodeName.SENTIMENT_ANALYZER.value
        else:
            entry_point = NodeName.AGENT.value

        self._workflow.set_entry_point(entry_point)

        logger.debug(f"Workflow entry point set to: {entry_point}")

    def _add_edges(self) -> None:
        logger.debug("Adding edges to workflow graph")

        if self._sentiment_node:
            self._workflow.add_edge(
                NodeName.SENTIMENT_ANALYZER.value,
                NodeName.AGENT.value
            )
            logger.debug("Added edge: sentiment -> agent")

        if self._tool_node:
            router = ToolCallRouter(
                max_iterations=self._agent_configuration.max_tool_iterations
            )

            self._workflow.add_conditional_edges(
                NodeName.AGENT.value,
                router.should_continue,
                {
                    "tools": NodeName.TOOLS.value,
                    END: END
                }
            )
            logger.debug("Added conditional edge: agent -> tools/END")

            self._workflow.add_edge(
                NodeName.TOOLS.value,
                NodeName.AGENT.value
            )
            logger.debug("Added edge: tools -> agent")
        else:
            self._workflow.add_edge(
                NodeName.AGENT.value,
                END
            )
            logger.debug("Added edge: agent -> END (no tools)")
