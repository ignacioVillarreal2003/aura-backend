from abc import ABC, abstractmethod
from typing import Optional, List

from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool


class LLMConfiguratorInterface(ABC):
    @abstractmethod
    def initialize(self) -> None:
        pass

    @abstractmethod
    async def call_llm(self,
                       llm: Runnable,
                       llm_input: List[BaseMessage]) -> BaseMessage:
        pass

    @abstractmethod
    async def call_llm_text(self,
                            llm: Runnable,
                            llm_input: List[BaseMessage]) -> str:
        pass

    @abstractmethod
    def get_llm_base(self) -> Runnable:
        pass

    @abstractmethod
    def get_llm_with_tools(self) -> Runnable:
        pass

    @property
    @abstractmethod
    def tools(self) -> List[BaseTool]:
        pass

    @property
    @abstractmethod
    def tool_instructions(self) -> Optional[str]:
        pass
