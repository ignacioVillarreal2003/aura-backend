import logging

from fastapi import APIRouter, Depends

from app.api.dependencies.idempotency import optional_idempotency_key
from app.api.dependencies.rate_limiter import strict_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.services.rag_agent_service.rag_agent_service import get_rag_agent_service
from app.application.services.rag_agent_service.interfaces.rag_agent_service_interface import RagAgentServiceInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.agent.agent_request import AgentRequest
from app.domain.dtos.agent.agent_response import AgentResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)


class RagAgentController:
    async def execute(
            self,
            agent_request: AgentRequest,
            rag_agent_service: RagAgentServiceInterface = Depends(get_rag_agent_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _idemp: None = Depends(optional_idempotency_key),
            _rl: None = Depends(strict_rate_limit),
    ) -> AgentResponse:
        logger.info(
            "Handling RAG agent request",
            extra={"user_id": authenticated_user.id},
        )

        response = await rag_agent_service.execute(
            agent_request=agent_request,
            authenticated_user=authenticated_user,
        )

        logger.info(
            "RAG agent request completed successfully",
            extra={"user_id": authenticated_user.id},
        )

        return response


router = APIRouter()
rag_agent_controller = RagAgentController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Respuesta del agente RAG",
        "model": AgentResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    rag_agent_controller.execute,
    methods=["POST"],
    response_model=AgentResponse,
    operation_id="executeRagAgent",
    summary="Ejecutar agente RAG",
    description=(
        "Ejecuta el agente RAG completo: analiza la consulta, recupera contexto documental, "
        "evalúa su suficiencia, razona sobre la respuesta y sintetiza la respuesta final."
    ),
    responses=_response,
)
