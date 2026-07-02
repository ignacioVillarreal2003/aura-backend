from abc import ABC, abstractmethod
from typing import Any, List, Optional
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool


class OllamaLLMFacadeInterface(ABC):
    @abstractmethod
    async def initialize(self) -> None:
        pass

    @abstractmethod
    async def get_llm_base(self) -> Runnable:
        pass

    @abstractmethod
    def apply_options(self, llm: Runnable, **overrides: Any) -> Runnable:
        pass

    @abstractmethod
    async def get_llm_json(self) -> Runnable:
        pass

    @abstractmethod
    async def get_llm_with_tools(self) -> Runnable:
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        pass

    @abstractmethod
    async def check_health(self) -> bool:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @property
    @abstractmethod
    def tools_bound(self) -> bool:
        pass

    @property
    @abstractmethod
    def tools(self) -> List[BaseTool]:
        pass

    @property
    @abstractmethod
    def tool_instructions(self) -> Optional[str]:
        pass
