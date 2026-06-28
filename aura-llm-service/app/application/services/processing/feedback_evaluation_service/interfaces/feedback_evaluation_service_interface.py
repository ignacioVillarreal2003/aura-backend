from abc import ABC, abstractmethod
from app.domain.dtos.user_interactions.feedback_evaluation.feedback_evaluation_request import FeedbackEvaluationRequest
from app.domain.dtos.user_interactions.feedback_evaluation.feedback_evaluation_response import FeedbackEvaluationResponse


class FeedbackEvaluationServiceInterface(ABC):
    @abstractmethod
    async def execute_feedback_evaluation(
            self,
            request: FeedbackEvaluationRequest,
    ) -> FeedbackEvaluationResponse:
        pass
