from fastapi import APIRouter

from app.api.controllers import (
    document_question_controller,
    document_summary_controller,
    document_action_controller,
    agent_controller,
    document_classify_controller,
    fragment_enrich_controller,
)

router = APIRouter()

router.include_router(
    document_question_controller.router,
    prefix="/document-question"
)

router.include_router(
    document_summary_controller.router,
    prefix="/document-summary"
)

router.include_router(
    document_action_controller.router,
    prefix="/document-action"
)

router.include_router(
    agent_controller.router,
    prefix="/agent"
)

router.include_router(
    document_classify_controller.router,
    prefix="/document-classify",
)

router.include_router(
    fragment_enrich_controller.router,
    prefix="/fragment-enrich",
)
