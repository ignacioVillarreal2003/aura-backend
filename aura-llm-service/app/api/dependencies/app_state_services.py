import logging
from collections.abc import Awaitable, Callable
from typing import Any
from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


def state_dependency(attribute: str, display_name: str) -> Callable[[Request], Awaitable[Any]]:
    async def _resolve(request: Request) -> Any:
        try:
            return getattr(request.app.state, attribute)
        except AttributeError as e:
            logger.error(
                "Service not found in application state.",
                extra={"state_attribute": attribute},
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{display_name} is not available",
            ) from e

    return _resolve


get_document_question_service = state_dependency("document_question_service", "DocumentQuestionService")
get_document_summary_service = state_dependency("document_summary_service", "DocumentSummaryService")
get_document_action_service = state_dependency("document_action_service", "DocumentActionService")
get_document_classify_service = state_dependency("document_classify_service", "DocumentClassifyService")
get_fragment_contextualize_service = state_dependency(
    "fragment_contextualize_service", "FragmentContextualizeService"
)
get_graph_extraction_service = state_dependency("graph_extraction_service", "GraphExtractionService")
get_graph_query_translation_service = state_dependency(
    "graph_query_translation_service", "GraphQueryTranslationService"
)
get_rag_agent_service = state_dependency("rag_agent_service", "RAG agent service")
get_general_chat_service = state_dependency("general_chat_service", "GeneralChatService")
get_report_service = state_dependency("report_service", "Report service")
get_checklist_service = state_dependency("checklist_service", "Checklist service")
get_timeline_service = state_dependency("timeline_service", "Timeline service")
get_quiz_service = state_dependency("quiz_service", "Quiz service")
get_lessons_learned_service = state_dependency("lessons_learned_service", "Lessons-learned service")
get_decision_brief_service = state_dependency("decision_brief_service", "Decision-brief service")
get_feedback_evaluation_service = state_dependency("feedback_evaluation_service", "FeedbackEvaluationService")

