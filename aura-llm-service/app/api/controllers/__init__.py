from fastapi import APIRouter
from app.api.controllers import question_controller, summary_controller

router = APIRouter()
router.include_router(question_controller.router, prefix="/questions")
router.include_router(summary_controller.router, prefix="/summaries")
