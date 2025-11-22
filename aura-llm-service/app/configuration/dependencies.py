from functools import lru_cache

from fastapi import Depends

from app.application.services.interfaces.question_service_interface import QuestionServiceInterface
from app.application.services.llm_service import LLMService
from app.application.services.question_service import QuestionService
from app.application.services.summary_service import SummaryService
from app.infrastructure.messaging.interfaces.question_listener_interface import QuestionListenerInterface
from app.infrastructure.messaging.question_listener import QuestionListener
from app.infrastructure.messaging.rabbitmq_client import RabbitmqClient


def get_question_service() -> QuestionService:
    return QuestionService(get_llm_service())


def get_summary_service() -> SummaryService:
    return SummaryService(get_llm_service())


def get_llm_service() -> LLMService:
    return LLMService()


@lru_cache
def get_rabbitmq_client() -> RabbitmqClient:
    return RabbitmqClient()


def get_question_listener(rabbitmq_client: RabbitmqClient = Depends(get_rabbitmq_client),
                          question_service: QuestionServiceInterface = Depends(get_question_service)) -> QuestionListenerInterface:
    return QuestionListener(rabbitmq_client,
                            question_service)