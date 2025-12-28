import logging
from typing import Callable, Optional, Iterable, List
from langchain_core.tools import BaseTool

from app.application.llm_facade.exceptions.llm_facade_exceptions import ToolInitializationError

logger = logging.getLogger(__name__)

ToolFactory = Callable[[], BaseTool]


class OllamaToolManager:
    def __init__(self,
                 tool_factories: Optional[Iterable[ToolFactory]] = None):
        self._factories: List[ToolFactory] = (
            list(tool_factories) if tool_factories else []
        )
        self._tools: List[BaseTool] = []
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            logger.debug("OllamaToolManager already initialized")
            return

        if not self._factories:
            logger.debug("No tool factories provided")
            self._tools = []
            self._initialized = True
            return

        created_tools: List[BaseTool] = []
        errors: List[tuple[int, Exception]] = []

        for idx, factory in enumerate(self._factories):
            try:
                tool = self._create_and_validate_tool(factory, idx)
                created_tools.append(tool)

            except Exception as e:
                logger.warning(
                    f"Tool factory {idx} failed",
                    extra={"factory_index": idx, "error": str(e)}
                )
                errors.append((idx, e))

        if errors and not created_tools:
            error_details = "; ".join(
                f"Factory {idx}: {str(err)}" for idx, err in errors
            )
            raise ToolInitializationError(
                f"All tool factories failed: {error_details}"
            )

        if errors:
            logger.warning(
                f"{len(errors)} tool factories failed, {len(created_tools)} succeeded"
            )

        self._tools = created_tools
        self._initialized = True

        logger.info(
            f"OllamaToolManager initialized with {len(created_tools)} tools"
        )

    @staticmethod
    def _create_and_validate_tool(factory: ToolFactory,
                                  factory_index: int) -> BaseTool:
        tool = factory()

        if not isinstance(tool, BaseTool):
            raise TypeError(
                f"Factory {factory_index} produced {type(tool).__name__}, "
                f"expected BaseTool"
            )

        if not hasattr(tool, "args_schema"):
            tool_name = getattr(tool, "name", "unknown")
            logger.warning(
                f"Tool '{tool_name}' missing args_schema",
                extra={
                    "tool_name": tool_name,
                    "factory_index": factory_index
                }
            )

        return tool

    @property
    def tools(self) -> List[BaseTool]:
        return self._tools.copy()

    @property
    def has_tools(self) -> bool:
        return len(self._tools) > 0

    def generate_instructions(self) -> Optional[str]:
        if not self._tools:
            return None

        lines = ["Tienes acceso a las siguientes herramientas:"]

        for tool in self._tools:
            tool_info = self._extract_tool_info(tool)
            lines.append(f"- {tool_info['name']}: {tool_info['description']}")

        lines.append(
            "\nUSA estas herramientas cuando sea apropiado para "
            "proporcionar respuestas precisas y útiles."
        )

        return "\n".join(lines)

    @staticmethod
    def _extract_tool_info(tool: BaseTool) -> dict:
        name = getattr(
            tool,
            "name",
            getattr(tool, "__class__", type(tool)).__name__
        )

        description = getattr(tool, "description", None)
        if not description:
            description = getattr(tool, "__doc__", "")

        if description:
            description = description.strip().split("\n")[0].strip()
        else:
            description = "No description available"

        return {
            "name": name,
            "description": description
        }
