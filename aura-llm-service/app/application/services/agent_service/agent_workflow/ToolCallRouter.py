from langchain_core.messages import BaseMessage


class ToolCallRouter:
    """
    Routes workflow based on tool calls.

    Prevents infinite loops with iteration limit.
    """

    def __init__(self, max_iterations: int = 5):
        """
        Initialize router.

        Args:
            max_iterations: Maximum tool call iterations allowed
        """
        self._max_iterations = max_iterations
        self._iteration_count = 0

    def should_continue(self, state: AgentState) -> str:
        """
        Decide whether to continue to tools or end.

        Args:
            state: Current agent state

        Returns:
            "tools" to continue, END to finish
        """
        logger.debug("Evaluating routing decision")

        messages = state.get("messages", [])

        if not messages:
            logger.warning("No messages in state, routing to END")
            self._iteration_count = 0
            return END

        last_message = messages[-1]

        # Check for tool calls
        has_tool_calls = self._has_tool_calls(last_message)

        if not has_tool_calls:
            logger.debug("No tool calls detected, routing to END")
            self._iteration_count = 0
            return END

        # Increment counter
        self._iteration_count += 1

        # Check iteration limit
        if self._iteration_count > self._max_iterations:
            logger.warning(
                f"Max tool iterations ({self._max_iterations}) exceeded, "
                "routing to END"
            )
            self._iteration_count = 0
            return END

        logger.debug(
            f"Tool calls detected (iteration {self._iteration_count}/"
            f"{self._max_iterations}), routing to tools"
        )

        return "tools"

    @staticmethod
    def _has_tool_calls(message: BaseMessage) -> bool:
        """Check if message contains tool calls."""
        # Check tool_calls attribute
        if hasattr(message, 'tool_calls') and message.tool_calls:
            return True

        # Check additional_kwargs
        if hasattr(message, 'additional_kwargs'):
            tool_calls = message.additional_kwargs.get('tool_calls')
            if tool_calls:
                return True

        return False