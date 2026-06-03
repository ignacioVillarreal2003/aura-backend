from fastapi import APIRouter, Depends

from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.lessons_learned_service.lessons_learned_service import get_lessons_learned_service
from app.application.services.lessons_learned_service.interfaces.lessons_learned_service_interface import (
    LessonsLearnedServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.lessons_learned.lessons_learned_request import LessonsLearnedGenerateRequest
from app.domain.dtos.lessons_learned.lessons_learned_response import LessonsLearnedGenerateResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class LessonsLearnedController:
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


router = APIRouter()
lessons_learned_controller = LessonsLearnedController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Lecciones aprendidas generadas exitosamente",
        "model": LessonsLearnedGenerateResponse,
    },
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
        "En modo `direct` analiza solo el texto provisto por el usuario. "
        "En modo `rag` recupera fragmentos relevantes de los documentos del usuario como contexto adicional. "
        "El campo `messages` actúa como historial: el último mensaje debe ser `human` con el "
        "relato a analizar o la instrucción de refinamiento."
    ),
    responses=_response,
)
