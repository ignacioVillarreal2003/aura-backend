import logging

from app.application.services.interfaces.question_service_interface import QuestionServiceInterface
from app.application.services.llm_service import LLMService
from app.domain.dtos.question_request import QuestionRequest
from app.domain.dtos.question_response import QuestionResponse
from app.application.exceptions.api_exceptions import LLMError

logger = logging.getLogger(__name__)


class QuestionService(QuestionServiceInterface):
    def __init__(self,
                 llm_service: LLMService):
        self.llm_client = llm_service

    def _build_message(self,
                       request: QuestionRequest) -> list[dict]:
        logger.debug("Building messages for LLM request.")

        system_prompt = (
            "Eres un asistente útil que responde únicamente basándose en el contexto proporcionado. "
            "La respuesta debe estar en formato Markdown e incluir títulos (`#`), subtítulos (`##`), listas (`-`), "
            "negritas (`**`) y tablas cuando corresponda. "
            "Si el contexto no contiene suficiente información para responder de manera precisa, "
            "indica claramente que la información no está disponible y ofrece una respuesta general relacionada al tema "
            "sin inventar datos. "
            "No incluyas explicaciones sobre tu proceso interno ni texto fuera de la respuesta."
        )

        if request.context:
            logger.debug("Adding context to LLM system prompt.")
            system_prompt += (
                f"\n\nContexto relevante:\n{request.context}\n\n"
                "Responde basándote principalmente en este contexto."
            )

        messages = [{"role": "system", "content": system_prompt}]

        if request.messages:
            logger.debug(f"Adding {len(request.messages)} previous messages to LLM input.")
            for message in request.messages:
                messages.append({
                    "role": message.role,
                    "content": message.content
                })

        question_prompt = (
            f"Basado en el contexto proporcionado, responde a la siguiente pregunta:\n{request.question}"
        )

        messages.append({"role": "user", "content": question_prompt})

        logger.debug("LLM messages successfully built.")
        return messages

    async def generate_response(self,
                                request: QuestionRequest) -> QuestionResponse:
        logger.info("Generating LLM response for incoming QuestionRequest.")

        try:
            messages = self._build_message(request)
            logger.debug(f"Sending {len(messages)} messages to LLM.")

            result = await self.llm_client.call(messages)

            content = result["message"]["content"]
            logger.info("LLM response successfully generated.")

            return QuestionResponse(answer=content)

        except LLMError as e:
            logger.error(f"LLMError occurred while generating response: {e.message} (code={e.code})")
            raise

        except Exception as e:
            logger.exception("Unexpected error in generate_response.")
            raise LLMError(
                f"Error generating response: {str(e)}",
                code="GENERATE_RESPONSE_ERROR"
            )
