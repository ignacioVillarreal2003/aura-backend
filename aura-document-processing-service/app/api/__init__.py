from fastapi import APIRouter

from app.api.controllers.create_document_controller.create_document_controller import create_document_controller
from app.api.controllers.delete_document_controller.document_deletion_controller import delete_document_controller
from app.api.controllers.document_query_controller.document_query_controller import document_query_controller
from app.api.controllers.retrieve_document_controller.retrieve_document_controller import retrieve_document_controller
from app.api.controllers.update_document_controller.update_document_controller import update_document_controller

router = APIRouter()

router.include_router(
    create_document_controller.router,
    prefix="/create-document",
    tags=["CreateDocument"]
)

router.include_router(
    delete_document_controller.router,
    prefix="/delete-document",
    tags=["DeleteDocument"]
)

router.include_router(
    document_query_controller.router,
    prefix="/document-query",
    tags=["DocumentQuery"]
)

router.include_router(
    retrieve_document_controller.router,
    prefix="/retrieve-document",
    tags=["RetrieveDocument"]
)

router.include_router(
    update_document_controller.router,
    prefix="/update-document",
    tags=["UpdateDocument"]
)



