from fastapi import APIRouter

from app.api.controllers import (
    document_summary,
    agent,
    document_question,
    document_classify,
    fragment_enrich,
    document_action,
)
from app.api.controllers.health import health_controller

router = APIRouter()

router.include_router(
    health_controller.router,
    tags=["health"],
)

router.include_router(
    document_question.router,
    prefix="/document-question",
    tags=["document-question"],
)

router.include_router(
    document_summary.router,
    prefix="/document-summary",
    tags=["document-summary"],
)

router.include_router(
    document_action.router,
    prefix="/document-action",
    tags=["document-action"],
)

router.include_router(
    agent.router,
    prefix="/agent",
    tags=["agent"],
)

router.include_router(
    document_classify.router,
    prefix="/document-classify",
    tags=["document-classify"],
)

router.include_router(
    fragment_enrich.router,
    prefix="/fragment-enrich",
    tags=["fragment-enrich"],
)
