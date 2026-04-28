import logging
from typing import Callable, Dict, List, Optional
from langchain_core.tools import BaseTool

from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_facade_exceptions import ToolInitializationError

logger = logging.getLogger(__name__)

ToolFactory = Callable[[], BaseTool]


class OllamaToolManager:
    def __init__(self, tool_factories: Optional[List[ToolFactory]] = None) -> None:
        self._tool_factories = tool_factories or []
        self._tools: List[BaseTool] = []
        self._instructions: Optional[str] = None
        self._initialized: bool = False

        logger.debug("OllamaToolManager created")

    def initialize(self) -> None:
        if self._initialized:
            logger.debug("OllamaToolManager already initialized.")
            return

        if not self._tool_factories:
            logger.debug("No tool factories provided — skipping tool initialization.")
            self._initialized = True
            return

        logger.info("Initializing OllamaToolManager")

        created_tools: List[BaseTool] = []
        errors: List[tuple[int, Exception]] = []

        for idx, factory in enumerate(self._tool_factories):
            try:
                tool = self._create_and_validate_tool(factory, idx)
                created_tools.append(tool)
                logger.debug(
                    "Tool created successfully",
                    extra={"tool_name": tool.name, "factory_index": idx},
                )
            except Exception as e:
                logger.warning(
                    "Tool factory failed",
                    extra={
                        "factory_index": idx,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    exc_info=True,
                )
                errors.append((idx, e))

        if errors and not created_tools:
            error_details = "; ".join(f"Factory {idx}: {err}" for idx, err in errors)
            logger.error(
                "All tool factories failed",
                extra={"failed_factories": len(errors), "error_details": error_details},
            )
            raise ToolInitializationError(f"All tool factories failed: {error_details}")

        if errors:
            logger.warning(
                "Some tool factories failed — continuing with partial toolset",
                extra={
                    "failed": len(errors),
                    "succeeded": len(created_tools),
                    "total": len(self._tool_factories),
                },
            )

        self._tools = created_tools
        self._instructions = self._build_instructions()
        self._initialized = True

        logger.info(
            "OllamaToolManager initialized successfully",
            extra={"tool_count": len(self._tools)},
        )

    @staticmethod
    def _create_and_validate_tool(factory: ToolFactory, factory_index: int) -> BaseTool:
        tool = factory()

        if not isinstance(tool, BaseTool):
            raise TypeError(
                f"Factory {factory_index} produced {type(tool).__name__}, expected BaseTool."
            )

        if not getattr(tool, "args_schema", None):
            logger.warning(
                "Tool missing args_schema — tool calling may be unreliable",
                extra={
                    "tool_name": getattr(tool, "name", "unknown"),
                    "factory_index": factory_index,
                },
            )

        return tool

    @property
    def tools(self) -> List[BaseTool]:
        return self._tools

    @property
    def has_tools(self) -> bool:
        return bool(self._tools)

    def generate_instructions(self) -> Optional[str]:
        return self._instructions

    def _build_instructions(self) -> Optional[str]:
        if not self._tools:
            return None

        lines = ["Tienes acceso a las siguientes herramientas:"]
        for tool in self._tools:
            info = self._extract_tool_info(tool)
            lines.append(f"- {info['name']}: {info['description']}")

        lines.append(
            "\nUSA estas herramientas cuando sea apropiado para "
            "proporcionar respuestas precisas y útiles."
        )

        return "\n".join(lines)

    @staticmethod
    def _extract_tool_info(tool: BaseTool) -> Dict[str, str]:
        name = getattr(tool, "name", type(tool).__name__)

        description = getattr(tool, "description", None) or getattr(tool, "__doc__", None)
        if description:
            description = description.strip().split("\n")[0].strip()
        else:
            description = "No description available"

        return {"name": name, "description": description}
