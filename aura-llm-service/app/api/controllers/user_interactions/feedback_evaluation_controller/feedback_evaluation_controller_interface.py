from abc import ABC, abstractmethod
from app.application.services.user_interactions.feedback_evaluation_service.interfaces.feedback_evaluation_service_interface import (
    FeedbackEvaluationServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.feedback_evaluation.feedback_evaluation_request import FeedbackEvaluationRequest
from app.domain.dtos.user_interactions.feedback_evaluation.feedback_evaluation_response import FeedbackEvaluationResponse


class FeedbackEvaluationControllerInterface(ABC):
    @abstractmethod
    async def execute_feedback_evaluation(
            self,
            feedback_evaluation_request: FeedbackEvaluationRequest,
            feedback_evaluation_service: FeedbackEvaluationServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> FeedbackEvaluationResponse:
        pass
