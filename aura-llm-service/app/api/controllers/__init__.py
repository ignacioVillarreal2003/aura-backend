from fastapi import APIRouter

from app.api.controllers import (
    document_summary_controller,
    agent_controller,
    document_question_controller,
    document_classify_controller,
    fragment_enrich_controller,
    document_action_controller,
    rag_agent_controller,
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
