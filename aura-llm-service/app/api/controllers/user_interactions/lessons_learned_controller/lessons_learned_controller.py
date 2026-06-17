from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.controllers.user_interactions.lessons_learned_controller.lessons_learned_controller_interface import (
    LessonsLearnedControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit, strict_rate_limit
from app.api.openapi.common import default_error_responses
from app.api.sse import sse_response
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.api.dependencies.app_state_services import get_lessons_learned_service
from app.application.services.user_interactions.lessons_learned_service.interfaces.lessons_learned_service_interface import (
    LessonsLearnedServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.lessons_learned.lessons_learned_request import LessonsLearnedGenerateRequest
from app.domain.dtos.user_interactions.lessons_learned.lessons_learned_response import LessonsLearnedGenerateResponse

from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class LessonsLearnedController(LessonsLearnedControllerInterface):
    async def generate(
            self,
            lessons_learned_request: LessonsLearnedGenerateRequest,
            lessons_learned_service: LessonsLearnedServiceInterface = Depends(get_lessons_learned_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> LessonsLearnedGenerateResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_LESSONS_LEARNED_GENERATE}),
        )

        return await lessons_learned_service.generate(
            request=lessons_learned_request,
            authenticated_user=authenticated_user,
        )

    async def generate_stream(
            self,
            lessons_learned_request: LessonsLearnedGenerateRequest,
            lessons_learned_service: LessonsLearnedServiceInterface = Depends(get_lessons_learned_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> StreamingResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_LESSONS_LEARNED_GENERATE}),
        )

        return sse_response(
            lessons_learned_service.generate_stream(
                request=lessons_learned_request,
                authenticated_user=authenticated_user,
            )
        )


router = APIRouter()
lessons_learned_controller = LessonsLearnedController()

_error = default_error_responses(include_400=True, include_502=True, include_503=True)
_response = {
    200: {"description": "Lecciones aprendidas generadas exitosamente", "model": LessonsLearnedGenerateResponse},
    **_error,
}
_response_stream = {
    200: {"description": "Stream SSE de la generación", "content": {"text/event-stream": {}}},
    **_error,
}

router.add_api_route(
    "",
    lessons_learned_controller.generate,
    methods=["POST"],
    response_model=LessonsLearnedGenerateResponse,
    operation_id="generateLessonsLearned",
    summary="Generar lecciones aprendidas",
    description=(
        "Genera un análisis post-acción (lecciones aprendidas) a partir del relato de una operación o ejercicio. "
        "En modo `direct` analiza solo el texto provisto. "
        "En modo `rag` recupera fragmentos relevantes de los documentos del usuario."
    ),
    responses=_response,
)

router.add_api_route(
    "/stream",
    lessons_learned_controller.generate_stream,
    methods=["POST"],
    response_class=StreamingResponse,
    operation_id="generateLessonsLearnedStream",
    summary="Generar lecciones aprendidas (SSE)",
    description=(
        "Server-Sent Events: JSON lines con prefijo `data: `. "
        "Tipos de evento: `progress`, `complete`, `error` (campo discriminador `type`)."
    ),
    responses=_response_stream,
)
