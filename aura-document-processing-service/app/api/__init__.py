from fastapi import APIRouter

from app.api import (
    document_context_controller,
    document_creation_controller
)

router = APIRouter()

router.include_router(
    document_context_controller.router,
    prefix="/document-context",
    tags=["DocumentContext"]
)

router.include_router(
    document_creation_controller.router,
    prefix="/document-creation",
    tags=["DocumentCreation"]
)