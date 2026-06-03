from fastapi import APIRouter

from app.api.controllers import (
    document_summary_controller,
    agent_controller,
    document_question_controller,
    document_classify_controller,
    fragment_enrich_controller,
    document_action_controller,
    rag_agent_controller,
    graph_extraction_controller,
    graph_query_translation_controller,
    general_chat_controller,
    report_controller,
    checklist_controller,
    timeline_controller,
    quiz_controller,
    lessons_learned_controller,
    decision_brief_controller,
)
from app.api.controllers.health_controller import health_controller

router = APIRouter()

router.include_router(
    health_controller.router,
    tags=["health"],
)

router.include_router(
    document_question_controller.router,
    prefix="/document-question",
    tags=["document-question"],
)

router.include_router(
    document_summary_controller.router,
    prefix="/document-summary",
    tags=["document-summary"],
)

router.include_router(
    document_action_controller.router,
    prefix="/document-action",
    tags=["document-action"],
)

router.include_router(
    agent_controller.router,
    prefix="/agent",
    tags=["agent"],
)

router.include_router(
    document_classify_controller.router,
    prefix="/document-classify",
    tags=["document-classify"],
)

router.include_router(
    fragment_enrich_controller.router,
    prefix="/fragment-enrich",
    tags=["fragment-enrich"],
)

router.include_router(
    rag_agent_controller.router,
    prefix="/rag-agent",
    tags=["rag-agent"],
)

router.include_router(
    graph_extraction_controller.router,
    prefix="/graph-extraction",
    tags=["graph-extraction"],
)

router.include_router(
    graph_query_translation_controller.router,
    prefix="/graph-query-translation",
    tags=["graph-query-translation"],
)

router.include_router(
    general_chat_controller.router,
    prefix="/general-chat",
    tags=["general-chat"],
)

router.include_router(
    report_controller.router,
    prefix="/report-generate",
    tags=["report"],
)

router.include_router(
    checklist_controller.router,
    prefix="/checklist-generate",
    tags=["checklist"],
)

router.include_router(
    timeline_controller.router,
    prefix="/timeline-generate",
    tags=["timeline"],
)

router.include_router(
    quiz_controller.router,
    prefix="/quiz-generate",
    tags=["quiz"],
)

router.include_router(
    lessons_learned_controller.router,
    prefix="/lessons-learned-generate",
    tags=["lessons-learned"],
)

router.include_router(
    decision_brief_controller.router,
    prefix="/decision-brief-generate",
    tags=["decision-brief"],
)
