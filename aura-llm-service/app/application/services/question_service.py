import logging

from app.application.services.llm_service import LLMService
from app.domain.dtos.question_request import QuestionRequest
from app.domain.dtos.question_response import QuestionResponse
from app.application.exceptions.api_exceptions import LLMError


logger = logging.getLogger(__name__)


class QuestionService:
    def __init__(self,
             llm_service: LLMService):
        self.llm_client = llm_service

    def _build_messages(self, request: QuestionRequest) -> list[dict]:
        system_prompt = "Eres un asistente útil que responde preguntas basándose en el contexto proporcionado."
        if request.context:
            system_prompt += f"\n\nContexto relevante:\n{request.context}\n\nResponde basándote principalmente en este contexto."

        messages = [{"role": "system", "content": system_prompt}]
        if request.messages:
            messages.extend([{"role": msg.role, "content": msg.content} for msg in request.messages])
        messages.append({"role": "user", "content": request.question})
        return messages

    async def generate_response(self, request: QuestionRequest) -> QuestionResponse:
        try:
            logger.info(f"Generando respuesta para pregunta: {request.question[:50]}...")
            messages = self._build_messages(request)
            result = await self.llm_client.call(messages)
            content = result["message"]["content"]
            logger.info(f"Respuesta generada exitosamente ({len(content)} caracteres)")
            return QuestionResponse(question=request.question, response=content)
        except LLMError:
            raise
        except Exception as e:
            logger.error(f"Error inesperado en generate_response: {str(e)}", exc_info=True)
            raise LLMError(f"Error al generar la respuesta: {str(e)}", code="GENERATE_RESPONSE_ERROR")