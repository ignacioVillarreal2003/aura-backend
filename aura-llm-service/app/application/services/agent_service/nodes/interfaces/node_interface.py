from abc import ABC, abstractmethod
from typing import Dict, Any

from app.domain.agent_state.agent_state import AgentState


class NodeInterface(ABC):
    @abstractmethod
    async def process(self,
                      state: AgentState) -> Dict[str, Any]:
        pass

    async def __call__(self,
                       state: AgentState) -> Dict[str, Any]:
        return await self.process(state)
