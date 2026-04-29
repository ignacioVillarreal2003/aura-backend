from fastapi import APIRouter

from app.api.controllers.fragment import (
    fragment_query_router,
    post_process_fragment_router,
)
from app.api.controllers.document import (
    create_document_router,
    delete_document_router,
    document_download_router,
    document_query_router,
    post_process_document_router,
)
from app.api.controllers.health_controller import health_controller

router = APIRouter()

router.include_router(
    health_controller.router,
    tags=["health"],
)

router.include_router(
    delete_document_router,
    prefix="/delete-document",
    tags=["delete-document"],
)

router.include_router(
    create_document_router,
    prefix="/create-document",
    tags=["create-document"],
)

router.include_router(
    document_query_router,
    prefix="/document-query",
    tags=["document-query"],
)

router.include_router(
    document_download_router,
    prefix="/document-download",
    tags=["document-download"],
)

router.include_router(
    fragment_query_router,
    prefix="/fragment-query",
    tags=["fragment-query"],
)

router.include_router(
    post_process_document_router,
    prefix="/post-process-document",
    tags=["post-process-document"],
)

router.include_router(
    post_process_fragment_router,
    prefix="/post-process-fragment",
    tags=["post-process-fragment"],
)
