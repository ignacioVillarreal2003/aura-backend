from functools import lru_cache

from app.application.services.llm_service import LLMService
from app.application.services.question_service import QuestionService
from app.application.services.summary_service import SummaryService


@lru_cache()
def get_question_service() -> QuestionService:
    return QuestionService(get_llm_service())

@lru_cache()
def get_summary_service():
    return SummaryService(get_llm_service())

@lru_cache()
def get_llm_service():
    return LLMService()