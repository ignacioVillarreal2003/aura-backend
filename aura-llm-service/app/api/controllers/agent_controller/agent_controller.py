from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.dependencies.idempotency import optional_idempotency_key
from app.api.dependencies.rate_limiter import strict_rate_limit
from app.api.controllers.agent_controller.agent_controller_interface import (
    AgentControllerInterface
)
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.agent_service.agent_service import get_agent_service
from app.application.services.agent_service.interfaces.agent_service_interface import AgentServiceInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.agent.agent_request import AgentRequest
from app.domain.dtos.agent.agent_response import AgentResponse
from app.domain.dtos.agent.agent_stream_events import AgentStreamEvent
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class AgentController(AgentControllerInterface):
    async def execute_agent(
            self,
            agent_request: AgentRequest,
            agent_service: AgentServiceInterface = Depends(get_agent_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _idemp: None = Depends(optional_idempotency_key),
            _rl: None = Depends(strict_rate_limit),
    ) -> AgentResponse:
        return await agent_service.execute_agent(
            agent_request=agent_request,
            authenticated_user=authenticated_user
        )

    async def execute_agent_stream(
            self,
            agent_request: AgentRequest,
            agent_service: AgentServiceInterface = Depends(get_agent_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> StreamingResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_AGENT}),
        )

        async def sse_bytes() -> AsyncIterator[bytes]:
            async for event in agent_service.execute_agent_stream(
                    agent_request=agent_request,
                    authenticated_user=authenticated_user,
            ):
                yield _format_sse_event(event).encode("utf-8")

        return StreamingResponse(
            sse_bytes(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )


def _format_sse_event(event: AgentStreamEvent) -> str:
    return f"data: {event.model_dump_json()}\n\n"


router = APIRouter()
agent_controller = AgentController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Respuesta del agente",
        "model": AgentResponse,
    },
    **_error,
}
_response_stream = {
    200: {
        "description": "Stream SSE del agente",
        "content": {"text/event-stream": {}},
    },
    **_error,
}

router.add_api_route(
    "",
    agent_controller.execute_agent,
    methods=["POST"],
    response_model=AgentResponse,
    operation_id="executeAgent",
    summary="Ejecutar agente con herramientas",
    description="Ejecuta el agente con acceso a herramientas de pregunta y resumen sobre documentos.",
    responses=_response,
)

router.add_api_route(
    "/stream",
    agent_controller.execute_agent_stream,
    methods=["POST"],
    response_class=StreamingResponse,
    operation_id="executeAgentStream",
    summary="Ejecutar agente con herramientas (SSE)",
    description=(
        "Server-Sent Events: JSON lines con prefijo `data: `. "
        "Tipos de evento: `progress`, `complete`, `error` (campo discriminador `type`). "
        "Los eventos `progress` indican la etapa actual del pipeline. "
        "El evento `complete` incluye la respuesta completa y los fragmentos utilizados."
    ),
    responses=_response_stream,
)
