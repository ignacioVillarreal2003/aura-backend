from abc import ABC, abstractmethod
from typing import Any, Dict

from app.application.services.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState


class RagNodeInterface(ABC):
    @abstractmethod
    async def process(self, state: RagAgentState) -> Dict[str, Any]:
        pass

    async def __call__(self, state: RagAgentState) -> Dict[str, Any]:
        return await self.process(state)
