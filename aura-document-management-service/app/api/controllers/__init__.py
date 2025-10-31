from fastapi import APIRouter

from app.api.controllers import document_controller


router = APIRouter()

router.include_router(document_controller.router, prefix="/documents")