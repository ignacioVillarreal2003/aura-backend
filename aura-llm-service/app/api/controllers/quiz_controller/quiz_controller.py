from fastapi import APIRouter, Depends

from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.quiz_service.quiz_service import get_quiz_service
from app.application.services.quiz_service.interfaces.quiz_service_interface import QuizServiceInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.quiz.quiz_request import QuizGenerateRequest
from app.domain.dtos.quiz.quiz_response import QuizGenerateResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class QuizController:
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


router = APIRouter()
quiz_controller = QuizController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Cuestionario generado exitosamente",
        "model": QuizGenerateResponse,
    },
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
        "En modo `direct` analiza solo el texto provisto por el usuario. "
        "En modo `rag` recupera fragmentos relevantes de los documentos del usuario como contexto adicional. "
        "El campo `messages` actúa como historial: el último mensaje debe ser `human` con el "
        "material a evaluar o la instrucción de refinamiento."
    ),
    responses=_response,
)
