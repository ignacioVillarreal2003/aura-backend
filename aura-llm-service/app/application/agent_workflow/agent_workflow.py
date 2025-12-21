import logging
from typing import Dict, Any, List, Literal, Optional
from enum import Enum
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage

from app.application.nodes.agent_node import AgentNodeConfig, AgentNode, create_agent_node
from app.application.nodes.sentiment_node import SentimentNodeConfig, SentimentNode, create_sentiment_node
from app.application.ollama_configurator.ollama_configurator import OllamaConfigurator
from app.application.agent_state.agent_state import AgentState

logger = logging.getLogger(__name__)


class NodeName(str, Enum):
    SENTIMENT_ANALYZER = "sentiment_analyzer"
    AGENT = "agent"
    TOOLS = "tools"


class EdgeDecision(str, Enum):
    CONTINUE_TO_TOOLS = "tools"
    END = END


class AgentWorkflow:
    def __init__(self,
                 enable_sentiment_analysis: bool = True,
                 max_tool_iterations: int = 5,
                 sentiment_config: Optional[SentimentNodeConfig] = None,
                 agent_config: Optional[AgentNodeConfig] = None):
        self.enable_sentiment_analysis = enable_sentiment_analysis
        self.max_tool_iterations = max_tool_iterations
        self.sentiment_config = sentiment_config or SentimentNodeConfig()
        self.agent_config = agent_config or AgentNodeConfig()


class AgentWorkflowBuilder:
    def __init__(self,
                 state_schema: type,
                 configurator: OllamaConfigurator,
                 config: Optional[AgentWorkflow] = None):
        self.configurator = configurator
        self.config = config or AgentWorkflow()

        self.workflow = StateGraph(state_schema)

        self.sentiment_node: Optional[SentimentNode] = None
        self.agent_node: Optional[AgentNode] = None
        self.tool_node: Optional[ToolNode] = None

        self._tool_iteration_count: int = 0

        logger.info("AgentWorkflowBuilder initialized")

        self._build_graph()

    def _build_graph(self) -> None:
        try:
            logger.debug("Building workflow agent_state")

            self._create_nodes()
            self._add_nodes()

            self._set_entry_point()

            self._add_edges()

            logger.info("Workflow agent_state built successfully")

        except Exception:
            logger.critical("Failed to build workflow agent_state")
            raise

    def _create_nodes(self) -> None:
        logger.debug("Creating workflow nodes")

        if self.config.enable_sentiment_analysis:
            self.sentiment_node = create_sentiment_node(
                self.configurator,
                self.config.sentiment_config
            )
            logger.debug("Sentiment node created")

        self.agent_node = create_agent_node(
            self.configurator,
            self.config.agent_config
        )
        logger.debug("Agent node created")

        if self.configurator.tools_count > 0:
            tools = self._get_tools_from_configurator()
            self.tool_node = ToolNode(tools)
            logger.debug(f"Tool node created with {len(tools)} tools")
        else:
            logger.warning("No tools available, tool node will not be created")

    def _get_tools_from_configurator(self) -> List[Any]:
        if hasattr(self.configurator, '_tools'):
            return self.configurator._tools

        logger.warning(
            "Configurator doesn't expose _tools directly, "
            "attempting to extract from LLM"
        )

        llm_with_tools = self.configurator.get_llm_with_tools()

        if hasattr(llm_with_tools, 'bound_tools'):
            return llm_with_tools.bound_tools

        raise AttributeError(
            "Cannot extract tools from configurator. "
            "Ensure OllamaConfigurator exposes tools."
        )

    def _add_nodes(self) -> None:
        logger.debug("Adding nodes to workflow agent_state")

        if self.sentiment_node is not None:
            self.workflow.add_node(
                NodeName.SENTIMENT_ANALYZER.value,
                self.sentiment_node
            )
            logger.debug(f"Added node: {NodeName.SENTIMENT_ANALYZER.value}")

        # Add agent node
        if self.agent_node is None:
            raise RuntimeError("Agent node must be created before adding to agent_state")

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
        if self.config.enable_sentiment_analysis and self.sentiment_node is not None:
            entry_point = NodeName.SENTIMENT_ANALYZER.value
        else:
            entry_point = NodeName.AGENT.value

        self.workflow.set_entry_point(entry_point)

        logger.debug(f"Entry point set to: {entry_point}")

    def _add_edges(self) -> None:
        logger.debug("Adding edges to workflow agent_state")

        if self.config.enable_sentiment_analysis and self.sentiment_node is not None:
            self.workflow.add_edge(
                NodeName.SENTIMENT_ANALYZER.value,
                NodeName.AGENT.value
            )
            logger.debug(
                f"Added edge: {NodeName.SENTIMENT_ANALYZER.value} -> {NodeName.AGENT.value}"
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
            logger.debug(
                f"Added conditional edges from {NodeName.AGENT.value}"
            )

            self.workflow.add_edge(
                NodeName.TOOLS.value,
                NodeName.AGENT.value
            )
            logger.debug(
                f"Added edge: {NodeName.TOOLS.value} -> {NodeName.AGENT.value}"
            )
        else:
            self.workflow.add_edge(
                NodeName.AGENT.value,
                END
            )
            logger.debug(
                f"Added edge: {NodeName.AGENT.value} -> END (no tools)"
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

        if self._tool_iteration_count > self.config.max_tool_iterations:
            logger.warning(
                f"Max tool iterations ({self.config.max_tool_iterations}) exceeded, "
                "routing to END to prevent infinite loop"
            )
            self._tool_iteration_count = 0
            return END

        logger.debug(
            f"Tool calls detected (iteration {self._tool_iteration_count}/"
            f"{self.config.max_tool_iterations}), routing to tools"
        )
        return EdgeDecision.CONTINUE_TO_TOOLS.value

    def _has_tool_calls(self, message: BaseMessage) -> bool:
        if hasattr(message, 'tool_calls') and message.tool_calls:
            return True

        if hasattr(message, 'additional_kwargs'):
            tool_calls = message.additional_kwargs.get('tool_calls')
            if tool_calls:
                return True

        return False

    def compile(self):
        logger.info("Compiling workflow agent_state")

        try:
            compiled = self.workflow.compile()

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
            logger.error(
                "Failed to generate agent_state visualization",
                exc_info=True
            )
            return f"Error generating visualization: {e}"


def create_agent_workflow(configurator: OllamaConfigurator,
                          config: Optional[AgentWorkflow] = None):
    builder = AgentWorkflowBuilder(
        state_schema=AgentState,
        configurator=configurator,
        config=config
    )

    return builder.compile()


def get_default_workflow(configurator: OllamaConfigurator):
    return create_agent_workflow(configurator)
