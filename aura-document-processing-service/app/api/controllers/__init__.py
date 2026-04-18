from fastapi import APIRouter

from app.api.controllers.fragment_controllers import (
    fragment_query_controller,
    post_process_fragment_controller
)
from app.api.controllers.document_controllers import (
    create_document_controller,
    delete_document_controller,
    document_query_controller,
    document_download_controller,
    post_process_document_controller
)

router = APIRouter()

router.include_router(
    delete_document_controller.router,
    prefix="/delete-document",
    tags=["delete-document"]
)

router.include_router(
    create_document_controller.router,
    prefix="/create-document",
    tags=["create-document"]
)

router.include_router(
    document_query_controller.router,
    prefix="/document-query",
    tags=["document-query"]
)

router.include_router(
    document_download_controller.router,
    prefix="/document-download",
    tags=["document-download"]
)

router.include_router(
    fragment_query_controller.router,
    prefix="/fragment-query",
    tags=["fragment-query"]
)

router.include_router(
    post_process_document_controller.router,
    prefix="/post-process-document",
    tags=["post-process-document"]
)

router.include_router(
    post_process_fragment_controller.router,
    prefix="/post-process-fragment",
    tags=["post-process-fragment"]
)
