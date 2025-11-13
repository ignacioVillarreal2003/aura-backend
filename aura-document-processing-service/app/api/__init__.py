from fastapi import APIRouter

from app.api import document_controller, retrieval_controller

router = APIRouter()

router.include_router(document_controller.router, prefix="/documents")
router.include_router(retrieval_controller.router, prefix="/retrieval")