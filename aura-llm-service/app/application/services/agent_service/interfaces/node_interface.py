from abc import ABC, abstractmethod
from typing import Dict, Any

from app.application.services.agent_service.agent_state.agent_state import AgentState


class NodeInterface(ABC):
    @abstractmethod
    async def process(self,
                      agent_state: AgentState) -> Dict[str, Any]:
        pass

    async def __call__(self,
                       agent_state: AgentState) -> Dict[str, Any]:
        return await self.process(agent_state)
