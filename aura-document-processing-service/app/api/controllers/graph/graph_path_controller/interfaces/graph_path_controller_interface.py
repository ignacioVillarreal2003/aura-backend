from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.graph.graph_path_service.interfaces.graph_path_service_interface import (
    GraphPathServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_path.find_path_request import FindPathRequest
from app.domain.dtos.graph.graph_path.graph_path_response import FindPathResponse


class GraphPathControllerInterface(ABC):
    @abstractmethod
    async def find_paths(
            self,
            find_path_request: FindPathRequest,
            graph_path_service: GraphPathServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> FindPathResponse:
        pass
