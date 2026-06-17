from abc import ABC, abstractmethod
from typing import List
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable


class OllamaLLMInvokerInterface(ABC):
    @abstractmethod
    async def call_llm(
            self,
            llm: Runnable,
            llm_input: List[BaseMessage],
    ) -> BaseMessage:
        pass

    @abstractmethod
    async def call_llm_content(
            self,
            llm: Runnable,
            llm_input: List[BaseMessage],
    ) -> str:
        pass
