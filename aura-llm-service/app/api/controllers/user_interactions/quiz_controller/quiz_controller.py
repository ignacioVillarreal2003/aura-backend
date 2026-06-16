from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.controllers.user_interactions.quiz_controller.quiz_controller_interface import (
    QuizControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit, strict_rate_limit
from app.api.openapi.common import default_error_responses
from app.api.sse import sse_response
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.api.dependencies.app_state_services import get_quiz_service
from app.application.services.user_interactions.quiz_service.interfaces.quiz_service_interface import QuizServiceInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.quiz.quiz_request import QuizGenerateRequest
from app.domain.dtos.user_interactions.quiz.quiz_response import QuizGenerateResponse

from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class QuizController(QuizControllerInterface):
    async def generate(
            self,
            quiz_request: QuizGenerateRequest,
            quiz_service: QuizServiceInterface = Depends(get_quiz_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> QuizGenerateResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_QUIZ_GENERATE}),
        )

        return await quiz_service.generate(
            request=quiz_request,
            authenticated_user=authenticated_user,
        )

    async def generate_stream(
            self,
            quiz_request: QuizGenerateRequest,
            quiz_service: QuizServiceInterface = Depends(get_quiz_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> StreamingResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_QUIZ_GENERATE}),
        )

        return sse_response(
            quiz_service.generate_stream(
                request=quiz_request,
                authenticated_user=authenticated_user,
            )
        )


router = APIRouter()
quiz_controller = QuizController()

_error = default_error_responses(include_400=True, include_502=True, include_503=True)
_response = {
    200: {"description": "Cuestionario generado exitosamente", "model": QuizGenerateResponse},
    **_error,
}
_response_stream = {
    200: {"description": "Stream SSE de la generación", "content": {"text/event-stream": {}}},
    **_error,
}

router.add_api_route(
    "",
    quiz_controller.generate,
    methods=["POST"],
    response_model=QuizGenerateResponse,
    operation_id="generateQuiz",
    summary="Generar cuestionario de evaluación",
    description=(
        "Genera un cuestionario de evaluación a partir de material de capacitación. "
        "En modo `direct` analiza solo el texto provisto. "
        "En modo `rag` recupera fragmentos relevantes de los documentos del usuario."
    ),
    responses=_response,
)

router.add_api_route(
    "/stream",
    quiz_controller.generate_stream,
    methods=["POST"],
    response_class=StreamingResponse,
    operation_id="generateQuizStream",
    summary="Generar cuestionario (SSE)",
    description=(
        "Server-Sent Events: JSON lines con prefijo `data: `. "
        "Tipos de evento: `progress`, `complete`, `error` (campo discriminador `type`)."
    ),
    responses=_response_stream,
)
