import logging
from typing import Final
from langchain_core.messages import BaseMessage
from langgraph.constants import END

from app.application.services.agent_service.agent_state.agent_state import AgentState

logger = logging.getLogger(__name__)


class ToolCallRouter:
    DEFAULT_MAX_ITERATIONS: Final[int] = 5

    def __init__(self, max_iterations: int = DEFAULT_MAX_ITERATIONS) -> None:
        self.max_iterations = max_iterations
        self._iteration_count: int = 0
        logger.debug("ToolCallRouter initialized", extra={"max_iterations": max_iterations})

    def should_continue(self, agent_state: AgentState) -> str:
        logger.debug("Evaluating routing decision")

        messages = agent_state.get("messages", [])

        if not messages:
            logger.warning("No messages in state — routing to END")
            self._reset_counter()
            return END

        last_message = messages[-1]

        if not self._has_tool_calls(last_message):
            logger.debug("No tool calls detected — routing to END")
            self._reset_counter()
            return END

        self._iteration_count += 1

        if self._iteration_count > self.max_iterations:
            logger.warning(
                "Max tool iterations exceeded — routing to END",
                extra={
                    "iteration_count": self._iteration_count,
                    "max_iterations": self.max_iterations
                }
            )
            self._reset_counter()
            return END

        logger.debug(
            "Tool calls detected — routing to tools",
            extra={
                "iteration_count": self._iteration_count,
                "max_iterations": self.max_iterations
            }
        )
        return "tools"

    def _reset_counter(self) -> None:
        if self._iteration_count > 0:
            logger.debug("Resetting iteration counter")
            self._iteration_count = 0

    @staticmethod
    def _has_tool_calls(message: BaseMessage) -> bool:
        if hasattr(message, "tool_calls") and message.tool_calls:
            return True
        if hasattr(message, "additional_kwargs"):
            if message.additional_kwargs.get("tool_calls"):
                return True
        return False
