import logging
from enum import Enum
from langchain_core.messages import BaseMessage
from langgraph.constants import END

from app.application.services.agent_service.agent_state.agent_state import AgentState

logger = logging.getLogger(__name__)


class NodeName(str, Enum):
    SENTIMENT_ANALYZER = "sentiment_analyzer"
    AGENT = "agent"
    TOOLS = "tools"


class ToolCallRouter:
    def __init__(self,
                 max_iterations: int = 5) -> None:
        self._max_iterations = max_iterations
        self._iteration_count = 0

        logger.debug(
            "ToolCallRouter initialized",
            extra={"max_iterations": max_iterations}
        )

    def should_continue(self,
                        state: AgentState) -> str:
        logger.debug("Evaluating routing decision")

        messages = state.get("messages", [])

        if not messages:
            logger.warning("No messages in state, routing to END")
            self._reset_counter()
            return END

        last_message = messages[-1]

        has_tool_calls = self._has_tool_calls(last_message)

        if not has_tool_calls:
            logger.debug("No tool calls detected, routing to END")
            self._reset_counter()
            return END

        self._iteration_count += 1

        if self._iteration_count > self._max_iterations:
            logger.warning(
                f"Max tool iterations ({self._max_iterations}) exceeded, routing to END",
                extra={
                    "iteration_count": self._iteration_count,
                    "max_iterations": self._max_iterations
                }
            )
            self._reset_counter()
            return END

        logger.debug(
            f"Tool calls detected, routing to tools",
            extra={
                "iteration": self._iteration_count,
                "max_iterations": self._max_iterations
            }
        )

        return "tools"

    def _reset_counter(self) -> None:
        if self._iteration_count > 0:
            logger.debug(f"Resetting iteration counter (was at {self._iteration_count})")
            self._iteration_count = 0

    @staticmethod
    def _has_tool_calls(message: BaseMessage) -> bool:
        if hasattr(message, 'tool_calls') and message.tool_calls:
            logger.debug("Tool calls detected via tool_calls attribute")
            return True

        if hasattr(message, 'additional_kwargs'):
            tool_calls = message.additional_kwargs.get('tool_calls')
            if tool_calls:
                logger.debug("Tool calls detected via additional_kwargs")
                return True

        return False
