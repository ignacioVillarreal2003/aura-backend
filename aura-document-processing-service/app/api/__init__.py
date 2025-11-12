from fastapi import APIRouter

from app.api import document_controller


router = APIRouter()

router.include_router(document_controller.router, prefix="/documents")