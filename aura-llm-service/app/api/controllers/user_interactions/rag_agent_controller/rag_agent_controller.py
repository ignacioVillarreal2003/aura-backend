from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.controllers.user_interactions.rag_agent_controller.rag_agent_controller_interface import (
    RagAgentControllerInterface,
)
from app.api.dependencies.rate_limiter import strict_rate_limit
from app.api.openapi.common import default_error_responses
from app.api.sse import sse_response
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.api.dependencies.app_state_services import get_rag_agent_service
from app.application.services.user_interactions.rag_agent_service.interfaces.rag_agent_service_interface import (
    RagAgentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.agent.agent_request import AgentRequest
from app.domain.dtos.user_interactions.agent.agent_response import AgentResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class RagAgentController(RagAgentControllerInterface):
    async def execute(
            self,
            agent_request: AgentRequest,
            rag_agent_service: RagAgentServiceInterface = Depends(get_rag_agent_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> AgentResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_AGENT}),
        )

        return await rag_agent_service.execute(
            agent_request=agent_request,
            authenticated_user=authenticated_user,
        )

    async def execute_stream(
            self,
            agent_request: AgentRequest,
            rag_agent_service: RagAgentServiceInterface = Depends(get_rag_agent_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> StreamingResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_AGENT}),
        )

        return sse_response(
            rag_agent_service.execute_stream(
                agent_request=agent_request,
                authenticated_user=authenticated_user,
            )
        )


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
_response_stream = {
    200: {
        "description": "Stream SSE del agente RAG",
        "content": {"text/event-stream": {}},
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

router.add_api_route(
    "/stream",
    rag_agent_controller.execute_stream,
    methods=["POST"],
    response_class=StreamingResponse,
    operation_id="executeRagAgentStream",
    summary="Ejecutar agente RAG (SSE)",
    description=(
        "Server-Sent Events: JSON lines con prefijo `data: `. "
        "Tipos de evento: `progress`, `complete`, `error` (campo discriminador `type`). "
        "Los eventos `progress` indican la etapa actual del pipeline. "
        "El evento `complete` incluye la respuesta completa y los fragmentos utilizados."
    ),
    responses=_response_stream,
)
