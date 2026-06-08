from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import List
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable


class OllamaLLMStreamingInvokerInterface(ABC):
    @abstractmethod
    async def stream_llm_content(
            self,
            llm: Runnable,
            llm_input: List[BaseMessage],
    ) -> AsyncIterator[str]:
        pass
