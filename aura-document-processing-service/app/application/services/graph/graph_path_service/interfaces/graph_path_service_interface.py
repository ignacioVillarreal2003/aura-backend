from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_path.find_path_request import FindPathRequest
from app.domain.dtos.graph.graph_path.graph_path_response import FindPathResponse


class GraphPathServiceInterface(ABC):
    @abstractmethod
    async def find_paths(
            self,
            *,
            request: FindPathRequest,
            authenticated_user: AuthenticatedUser,
            database_session: AsyncSession,
            authorization_header: Optional[str] = None,
    ) -> FindPathResponse:
        pass
