from abc import ABC, abstractmethod
from fastapi import Request
from fastapi.responses import JSONResponse


class HealthControllerInterface(ABC):
    @abstractmethod
    async def liveness(self) -> JSONResponse:
        pass

    @abstractmethod
    async def readiness(self, request: Request) -> JSONResponse:
        pass
