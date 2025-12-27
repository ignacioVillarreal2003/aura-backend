import logging
from typing import Any, List, Literal, Optional
from enum import Enum
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage

from app.application.llm_configurator.interfaces.llm_configurator_interface import LLMConfiguratorInterface
from app.application.nodes.agent_node import (
    AgentNode,
    create_agent_node
)
from app.application.nodes.sentiment_node import (
    SentimentNode,
    create_sentiment_node
)
from app.domain.agent_state.agent_state import AgentState

logger = logging.getLogger(__name__)


class NodeName(str, Enum):
    SENTIMENT_ANALYZER = "sentiment_analyzer"
    AGENT = "agent"
    TOOLS = "tools"


class EdgeDecision(str, Enum):
    CONTINUE_TO_TOOLS = "tools"
    END = END


class AgentWorkflowBuilder:
    def __init__(self,
                 state_schema: type,
                 llm_configurator: LLMConfiguratorInterface,
                 max_tool_iterations: int = 5):
        self._llm_configurator = llm_configurator
        self._max_tool_iterations = max_tool_iterations

        self._workflow = StateGraph(state_schema)

        self._sentiment_node: Optional[SentimentNode] = None
        self._agent_node: Optional[AgentNode] = None
        self._tool_node: Optional[ToolNode] = None

        self._tool_iteration_count: int = 0

        self._build_graph()

    def _build_graph(self) -> None:
        try:
            logger.debug("Building workflow")

            self._create_nodes()
            self._add_nodes()
            self._set_entry_point()
            self._add_edges()

            logger.info("Workflow built successfully")

        except Exception:
            logger.critical("Failed to build workflow")
            raise

    def _create_nodes(self) -> None:
        logger.debug("Creating workflow nodes")

        self.sentiment_node = create_sentiment_node(
            self._llm_configurator,
        )
        logger.debug("Sentiment node created")

        self.agent_node = create_agent_node(
            self._llm_configurator,
        )
        logger.debug("Agent node created")

        tools = self._get_tools_from_configurator()
        if tools:
            self.tool_node = ToolNode(tools)
            logger.debug("Tool node created")
        else:
            logger.warning("No tools available")

    def _get_tools_from_configurator(self) -> List[Any]:
        return self._llm_configurator.tools

    def _add_nodes(self) -> None:
        logger.debug("Adding nodes to workflow")

        if self.sentiment_node is not None:
            self.workflow.add_node(
                NodeName.SENTIMENT_ANALYZER.value,
                self.sentiment_node
            )
            logger.debug(f"Added node: {NodeName.SENTIMENT_ANALYZER.value}")

        if self.agent_node is None:
            raise RuntimeError("Agent node must be created before adding to graph")

        self.workflow.add_node(
            NodeName.AGENT.value,
            self.agent_node
        )
        logger.debug(f"Added node: {NodeName.AGENT.value}")

        if self.tool_node is not None:
            self.workflow.add_node(
                NodeName.TOOLS.value,
                self.tool_node
            )
            logger.debug(f"Added node: {NodeName.TOOLS.value}")

    def _set_entry_point(self) -> None:
        entry_point = NodeName.SENTIMENT_ANALYZER.value
        self.workflow.set_entry_point(entry_point)
        logger.debug(f"Entry point set to: {entry_point}")

    def _add_edges(self) -> None:
        logger.debug("Adding edges to workflow")

        self.workflow.add_edge(
            NodeName.SENTIMENT_ANALYZER.value,
            NodeName.AGENT.value
        )

        if self.tool_node is not None:
            self.workflow.add_conditional_edges(
                NodeName.AGENT.value,
                self._should_continue,
                {
                    EdgeDecision.CONTINUE_TO_TOOLS.value: NodeName.TOOLS.value,
                    EdgeDecision.END.value: END
                }
            )

            self.workflow.add_edge(
                NodeName.TOOLS.value,
                NodeName.AGENT.value
            )
        else:
            self.workflow.add_edge(
                NodeName.AGENT.value,
                END
            )

    def _should_continue(self,
                         state: AgentState) -> Literal["tools", END]:
        logger.debug("Evaluating routing decision")

        messages = state.get("messages", [])

        if not messages:
            logger.warning("No messages in state, routing to END")
            return END

        last_message = messages[-1]

        has_tool_calls = self._has_tool_calls(last_message)

        if not has_tool_calls:
            logger.debug("No tool calls detected, routing to END")
            self._tool_iteration_count = 0  # Reset counter
            return END

        self._tool_iteration_count += 1

        if self._tool_iteration_count > self._max_tool_iterations:
            logger.warning(
                f"Max tool iterations ({self._max_tool_iterations}) exceeded, "
                "routing to END to prevent infinite loop"
            )
            self._tool_iteration_count = 0
            return END

        logger.debug(
            f"Tool calls detected (iteration {self._tool_iteration_count}/"
            f"{self._max_tool_iterations}), routing to tools"
        )
        return EdgeDecision.CONTINUE_TO_TOOLS.value

    def _has_tool_calls(self,
                        message: BaseMessage) -> bool:
        if hasattr(message, 'tool_calls') and message.tool_calls:
            return True

        if hasattr(message, 'additional_kwargs'):
            tool_calls = message.additional_kwargs.get('tool_calls')
            if tool_calls:
                return True

        return False

    @property
    def workflow(self):
        return self._workflow

    def compile(self):
        logger.info("Compiling workflow")
        try:
            compiled = self._workflow.compile()
            logger.info("Workflow compiled successfully")
            return compiled
        except Exception:
            logger.critical("Failed to compile workflow")
            raise

    def get_graph_visualization(self) -> str:
        try:
            workflow = self.compile()
            return workflow.get_graph().draw_mermaid()
        except Exception as e:
            logger.error("Failed to generate graph visualization", exc_info=True)
            return f"Error generating visualization: {e}"


def create_agent_workflow(llm_configurator: LLMConfiguratorInterface):
    builder = AgentWorkflowBuilder(
        state_schema=AgentState,
        llm_configurator=llm_configurator
    )

    return builder.compile()


def get_default_workflow(llm_configurator: LLMConfiguratorInterface):
    return create_agent_workflow(llm_configurator)
