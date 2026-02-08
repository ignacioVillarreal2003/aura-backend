from abc import ABC, abstractmethod

from app.domain.dtos.health.health_response import HealthResponse


class HealthControllerInterface(ABC):
    @abstractmethod
    async def get_status(
            self
    ) -> HealthResponse:
        pass
