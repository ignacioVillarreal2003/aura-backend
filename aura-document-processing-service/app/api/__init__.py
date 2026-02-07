from fastapi import APIRouter

from app.api.controllers import (
    document_query_controller,
    document_creation_controller,
    document_retrieve_controller,
    document_deletion_controller,
    health_controller
)

router = APIRouter()

router.include_router(
    document_retrieve_controller.router,
    prefix="/document-retrieve",
    tags=["DocumentRetrieve"]
)

router.include_router(
    document_creation_controller.router,
    prefix="/document-creation",
    tags=["DocumentCreation"]
)

router.include_router(
    document_deletion_controller.router,
    prefix="/document-deletion",
    tags=["DocumentDeletion"]
)

router.include_router(
    document_query_controller.router,
    prefix="/document-query",
    tags=["DocumentQuery"]
)

router.include_router(
    health_controller.router,
    prefix="/health",
    tags=["Health"]
)
