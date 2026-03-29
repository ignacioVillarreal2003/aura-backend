from fastapi import APIRouter

from app.api.controllers.fragment_controllers import (
    fragment_query_controller,
    post_process_fragment_controller
)
from app.api.controllers.document_controllers import (
    create_document_controller,
    delete_document_controller,
    document_query_controller,
    post_process_document_controller
)

router = APIRouter()

router.include_router(
    delete_document_controller.router,
    prefix="/delete-document_controllers",
    tags=["delete-document_controllers"]
)

router.include_router(
    create_document_controller.router,
    prefix="/create-document_controllers",
    tags=["create-document_controllers"]
)

router.include_router(
    document_query_controller.router,
    prefix="/document_controllers-query",
    tags=["document_controllers-query"]
)

router.include_router(
    fragment_query_controller.router,
    prefix="/fragment_controllers-query",
    tags=["fragment_controllers-query"]
)

router.include_router(
    post_process_document_controller.router,
    prefix="/post-process-document_controllers",
    tags=["post-process-document_controllers"]
)

router.include_router(
    post_process_fragment_controller.router,
    prefix="/post-process-fragment_controllers",
    tags=["post-process-fragment_controllers"]
)
