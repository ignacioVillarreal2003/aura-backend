from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from app.application import ollama_configurator
from app.application.graph.agent_state import AgentState
from app.application.graph.nodes.agent_node import agent_node
from app.application.graph.nodes.sentiment_node import sentiment_node


class AgentWorkflowBuilder:
    """Clase responsable de construir y compilar el grafo de LangGraph."""

    def __init__(self,
                 state_schema: type,
                 configurator: ollama_configurator):
        self.workflow = StateGraph(state_schema)
        self.configurator = configurator
        self.tools = configurator.tools
        self._build_graph()

    def _should_continue(self,
                         state: AgentState):
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        return END

    def _build_graph(self):
        tool_node = ToolNode(self.tools)

        self.workflow.add_node("sentiment_analyzer", sentiment_node)
        self.workflow.add_node("agent", agent_node)
        self.workflow.add_node("tools", tool_node)

        self.workflow.set_entry_point("sentiment_analyzer")

        self.workflow.add_edge("sentiment_analyzer", "agent")

        self.workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "tools": "tools",
                END: END
            }
        )

        self.workflow.add_edge("tools", "agent")

    def compile(self):
        return self.workflow.compile()
