import json
from typing import Any, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, field_validator, model_validator

from app.application.services.processing.feedback_evaluation_service.exceptions.feedback_evaluation_service_exceptions import (
    FeedbackEvaluationServiceException,
)
from app.application.services.processing.feedback_evaluation_service.feedback_evaluation_prompt import (
    HUMAN_PROMPT,
    REPAIR_PROMPT,
    SYSTEM_PROMPT,
)
from app.application.services.processing.feedback_evaluation_service.feedback_evaluation_settings import (
    FeedbackEvaluationServiceSettings,
)
from app.application.services.processing.feedback_evaluation_service.interfaces.feedback_evaluation_service_interface import (
    FeedbackEvaluationServiceInterface,
)
from app.application.services.processing.structured_processing_service import StructuredProcessingService
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.processing.feedback_evaluation.feedback_evaluation_request import FeedbackEvaluationRequest
from app.domain.dtos.processing.feedback_evaluation.feedback_evaluation_response import FeedbackEvaluationResponse
from app.domain.types import UserId
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

_ALLOWED_CATEGORIES: frozenset[str] = frozenset(
    {"retrieval_miss", "hallucination", "reasoning", "style", "incomplete", "other", "no_failure"}
)
_DEFAULT_CATEGORY = "other"

_SYSTEM_USER = AuthenticatedUser(id=UserId(0), email="system@aura.local")


class _FeedbackVerdict(BaseModel):

    failure_category: str = _DEFAULT_CATEGORY
    failure_explanation: str = "No se proporcionó explicación."
    expected_output: str = ""
    confidence_score: float = 0.0

    model_config = {"extra": "ignore"}

    @model_validator(mode="before")
    @classmethod
    def _drop_nulls(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {key: value for key, value in data.items() if value is not None}
        return data

    @field_validator("failure_category", mode="before")
    @classmethod
    def _normalize_category(cls, value: Any) -> str:
        if not isinstance(value, str):
            return _DEFAULT_CATEGORY
        candidate = value.strip().lower()
        return candidate if candidate in _ALLOWED_CATEGORIES else _DEFAULT_CATEGORY

    @field_validator("confidence_score", mode="before")
    @classmethod
    def _clamp_confidence(cls, value: Any) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        if score != score:
            return 0.0
        return min(1.0, max(0.0, score))


class FeedbackEvaluationService(
    StructuredProcessingService[FeedbackEvaluationRequest, _FeedbackVerdict, FeedbackEvaluationResponse],
    FeedbackEvaluationServiceInterface,
):
    label = "feedback evaluation"
    exception_cls = FeedbackEvaluationServiceException
    parsed_model = _FeedbackVerdict
    llm_error_message = "El modelo juez no pudo evaluar el feedback."
    unexpected_error_message = "Error inesperado al evaluar el feedback."

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            feedback_evaluation_service_settings: Optional[FeedbackEvaluationServiceSettings] = None,
    ) -> None:
        super().__init__(ollama_llm_facade, ollama_llm_invoker)
        self._settings = feedback_evaluation_service_settings or FeedbackEvaluationServiceSettings()

    def _build_messages(
            self,
            request: FeedbackEvaluationRequest,
            authenticated_user: AuthenticatedUser,
    ) -> list[BaseMessage]:
        user_id = authenticated_user.id
        chat_history = self._truncate(
            json.dumps(request.chat_history, ensure_ascii=False, indent=2),
            self._settings.max_history_chars, user_id, "chat history",
        )
        fragments = self._truncate(
            json.dumps(request.fragments or [], ensure_ascii=False, indent=2),
            self._settings.max_fragments_chars, user_id, "fragments",
        )
        human_content = HUMAN_PROMPT.format(
            user_query=self._truncate(
                request.user_query, self._settings.max_query_chars, user_id, "user query"
            ),
            chat_history=chat_history,
            fragments=fragments,
            assistant_response=self._truncate(
                request.assistant_response, self._settings.max_response_chars, user_id, "assistant response"
            ),
            feedback_reason=request.feedback_reason or "N/A",
            feedback_comment=self._truncate(
                request.feedback_comment or "N/A", self._settings.max_comment_chars, user_id, "feedback comment"
            ),
            mode=request.mode,
        )
        return [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]

    def _max_repair_attempts(self, request: FeedbackEvaluationRequest) -> int:
        return self._settings.max_repair_attempts

    def _build_repair_messages(
            self,
            original_messages: list[BaseMessage],
            malformed_output: str,
            parse_error: str,
    ) -> list[BaseMessage]:
        repair = HumanMessage(
            content=REPAIR_PROMPT.format(
                parse_error=parse_error[:500],
                malformed_output=malformed_output[:2_000],
            )
        )
        return [*original_messages, repair]

    def _postprocess(
            self,
            parsed: _FeedbackVerdict,
            request: FeedbackEvaluationRequest,
            authenticated_user: AuthenticatedUser,
    ) -> FeedbackEvaluationResponse:
        return FeedbackEvaluationResponse(
            failure_category=parsed.failure_category,
            failure_explanation=parsed.failure_explanation,
            expected_output=parsed.expected_output,
            confidence_score=parsed.confidence_score,
            judge_model=self._ollama_llm_facade.model_name,
        )

    def _request_log_extra(
            self,
            request: FeedbackEvaluationRequest,
            authenticated_user: AuthenticatedUser,
    ) -> dict[str, Any]:
        return {
            "mode": request.mode,
            "feedback_reason": request.feedback_reason,
            "history_len": len(request.chat_history),
            "fragments_len": len(request.fragments or []),
        }

    def _result_log_extra(self, result: FeedbackEvaluationResponse) -> dict[str, Any]:
        return {
            "failure_category": result.failure_category,
            "confidence_score": result.confidence_score,
        }

    async def execute_feedback_evaluation(
            self,
            request: FeedbackEvaluationRequest,
    ) -> FeedbackEvaluationResponse:
        return await self._generate(request, _SYSTEM_USER)
