from fastapi import APIRouter, Depends

from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.controllers.user_interactions.feedback_evaluation_controller.feedback_evaluation_controller_interface import (
    FeedbackEvaluationControllerInterface,
)
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.api.dependencies.app_state_services import get_feedback_evaluation_service
from app.application.services.user_interactions.feedback_evaluation_service.interfaces.feedback_evaluation_service_interface import (
    FeedbackEvaluationServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.feedback_evaluation.feedback_evaluation_request import FeedbackEvaluationRequest
from app.domain.dtos.user_interactions.feedback_evaluation.feedback_evaluation_response import FeedbackEvaluationResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class FeedbackEvaluationController(FeedbackEvaluationControllerInterface):
    async def execute_feedback_evaluation(
            self,
            feedback_evaluation_request: FeedbackEvaluationRequest,
            feedback_evaluation_service: FeedbackEvaluationServiceInterface = Depends(get_feedback_evaluation_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> FeedbackEvaluationResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_FEEDBACK_EVALUATION}),
        )

        return await feedback_evaluation_service.execute_feedback_evaluation(
            request=feedback_evaluation_request,
        )


router = APIRouter()
feedback_evaluation_controller = FeedbackEvaluationController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Evaluación del feedback (auditoría juez LLM)",
        "model": FeedbackEvaluationResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    feedback_evaluation_controller.execute_feedback_evaluation,
    methods=["POST"],
    response_model=FeedbackEvaluationResponse,
    operation_id="executeFeedbackEvaluation",
    summary="Evaluar y auditar feedback negativo",
    description="Ejecuta LLM-as-a-judge para analizar dónde falló la respuesta conversacional y proponer corrección.",
    responses=_response,
)
