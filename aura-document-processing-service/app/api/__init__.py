from fastapi import APIRouter

from app.api.controllers import (
    update_document_controller,
    delete_document_controller,
    create_document_controller,
    document_query_controller
)

router = APIRouter()

router.include_router(
    update_document_controller.router,
    prefix="/update-document"
)

router.include_router(
    delete_document_controller.router,
    prefix="/delete-document"
)

router.include_router(
    create_document_controller.router,
    prefix="/create-document"
)

router.include_router(
    document_query_controller.router,
    prefix="/document-query"
)
