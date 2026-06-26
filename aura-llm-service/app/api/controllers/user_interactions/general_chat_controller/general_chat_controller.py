from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.dependencies.rate_limiter import default_rate_limit, strict_rate_limit
from app.api.controllers.user_interactions.general_chat_controller.general_chat_controller_interface import (
    GeneralChatControllerInterface,
)
from app.api.openapi.common import default_error_responses
from app.api.sse import sse_response
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.api.dependencies.app_state_services import get_general_chat_service
from app.application.services.user_interactions.general_chat_service.interfaces.general_chat_service_interface import (
    GeneralChatServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.general_chat.general_chat_request import GeneralChatRequest
from app.domain.dtos.user_interactions.general_chat.general_chat_response import GeneralChatResponse

from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class GeneralChatController(GeneralChatControllerInterface):
    async def execute_general_chat(
            self,
            general_chat_request: GeneralChatRequest,
            general_chat_service: GeneralChatServiceInterface = Depends(get_general_chat_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> GeneralChatResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_GENERAL_CHAT}),
        )

        return await general_chat_service.execute_general_chat(
            general_chat_request=general_chat_request,
            authenticated_user=authenticated_user,
        )

    async def execute_general_chat_stream(
            self,
            general_chat_request: GeneralChatRequest,
            general_chat_service: GeneralChatServiceInterface = Depends(get_general_chat_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> StreamingResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_GENERAL_CHAT}),
        )

        return sse_response(
            general_chat_service.execute_general_chat_stream(
                general_chat_request=general_chat_request,
                authenticated_user=authenticated_user,
            )
        )


router = APIRouter()
general_chat_controller = GeneralChatController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Respuesta del asistente",
        "model": GeneralChatResponse,
    },
    **_error,
}
_response_stream = {
    200: {
        "description": "Stream SSE de la respuesta",
        "content": {"text/event-stream": {}},
    },
    **_error,
}

router.add_api_route(
    "",
    general_chat_controller.execute_general_chat,
    methods=["POST"],
    response_model=GeneralChatResponse,
    operation_id="executeGeneralChat",
    summary="Chat de propósito general con el asistente",
    description=(
        "Envía un historial de mensajes al LLM y devuelve la respuesta del asistente. "
        "No utiliza RAG ni contexto documental — solo el historial de conversación."
    ),
    responses=_response,
)

router.add_api_route(
    "/stream",
    general_chat_controller.execute_general_chat_stream,
    methods=["POST"],
    response_class=StreamingResponse,
    operation_id="executeGeneralChatStream",
    summary="Chat de propósito general con el asistente (SSE)",
    description=(
        "Server-Sent Events: JSON lines con prefijo `data: `. "
        "Tipos de evento: `delta`, `complete`, `error` (campo discriminador `type`)."
    ),
    responses=_response_stream,
)
