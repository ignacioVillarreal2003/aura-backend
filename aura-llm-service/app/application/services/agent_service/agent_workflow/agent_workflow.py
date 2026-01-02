from enum import Enum


class NodeName(str, Enum):
    """Node names in workflow."""
    SENTIMENT_ANALYZER = "sentiment_analyzer"
    AGENT = "agent"
    TOOLS = "tools"


class AgentWorkflowBuilder:
    """Builds agent workflow with LangGraph."""

    def __init__(
            self,
            llm_configurator: LLMConfiguratorInterface,
            config: Optional[AgentConfig] = None,
            sentiment_config: Optional[SentimentConfig] = None,
            agent_config: Optional[AgentNodeConfig] = None
    ):
        """
        Initialize workflow builder.

        Args:
            llm_configurator: LLM configurator
            config: Agent configuration
            sentiment_config: Sentiment node configuration
            agent_config: Agent node configuration
        """
        self._llm_configurator = llm_configurator
        self._config = config or AgentConfig()
        self._sentiment_config = sentiment_config
        self._agent_config = agent_config

        # Create workflow
        self._workflow = StateGraph(AgentState)

        # Nodes (created lazily)
        self._sentiment_node: Optional[SentimentNode] = None
        self._agent_node: Optional[AgentNode] = None
        self._tool_node: Optional[ToolNode] = None

    async def build(self):
        """
        Build complete workflow.

        Returns:
            Compiled workflow
        """
        logger.debug("Building agent workflow")

        try:
            # Create nodes
            await self._create_nodes()

            # Add nodes to graph
            self._add_nodes()

            # Set entry point
            self._set_entry_point()

            # Add edges
            self._add_edges()

            # Compile
            compiled = self._workflow.compile()

            logger.info("Agent workflow built successfully")

            return compiled

        except Exception:
            logger.exception("Failed to build workflow")
            raise

    async def _create_nodes(self) -> None:
        """Create all workflow nodes."""
        logger.debug("Creating workflow nodes")

        # Create sentiment node (if enabled)
        if self._config.enable_sentiment_analysis:
            self._sentiment_node = SentimentNode(
                llm_configurator=self._llm_configurator,
                config=self._sentiment_config
            )
            logger.debug("Sentiment node created")

        # Create agent node
        self._agent_node = AgentNode(
            llm_configurator=self._llm_configurator,
            config=self._agent_config
        )
        logger.debug("Agent node created")

        # Create tool node (if tools available)
        tools = self._llm_configurator.tools
        if tools:
            self._tool_node = ToolNode(tools)
            logger.debug(f"Tool node created with {len(tools)} tools")

    def _add_nodes(self) -> None:
        """Add nodes to workflow graph."""
        logger.debug("Adding nodes to workflow")

        # Add sentiment node
        if self._sentiment_node:
            self._workflow.add_node(
                NodeName.SENTIMENT_ANALYZER.value,
                self._sentiment_node
            )

        # Add agent node (required)
        if self._agent_node is None:
            raise RuntimeError("Agent node must be created")

        self._workflow.add_node(
            NodeName.AGENT.value,
            self._agent_node
        )

        # Add tool node
        if self._tool_node:
            self._workflow.add_node(
                NodeName.TOOLS.value,
                self._tool_node
            )

    def _set_entry_point(self) -> None:
        """Set workflow entry point."""
        if self._sentiment_node:
            entry_point = NodeName.SENTIMENT_ANALYZER.value
        else:
            entry_point = NodeName.AGENT.value

        self._workflow.set_entry_point(entry_point)
        logger.debug(f"Entry point set to: {entry_point}")

    def _add_edges(self) -> None:
        """Add edges between nodes."""
        logger.debug("Adding edges to workflow")

        # Sentiment -> Agent (if sentiment enabled)
        if self._sentiment_node:
            self._workflow.add_edge(
                NodeName.SENTIMENT_ANALYZER.value,
                NodeName.AGENT.value
            )

        # Agent -> Tools or END
        if self._tool_node:
            # Create router with iteration limit
            router = ToolCallRouter(
                max_iterations=self._config.max_tool_iterations
            )

            self._workflow.add_conditional_edges(
                NodeName.AGENT.value,
                router.should_continue,
                {
                    "tools": NodeName.TOOLS.value,
                    END: END
                }
            )

            # Tools -> Agent (loop back)
            self._workflow.add_edge(
                NodeName.TOOLS.value,
                NodeName.AGENT.value
            )
        else:
            # No tools, go directly to END
            self._workflow.add_edge(
                NodeName.AGENT.value,
                END
            )
