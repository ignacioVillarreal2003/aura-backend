import logging
import asyncio
from typing import List

from app.application.exceptions.api_exceptions import LLMError
from app.domain.dtos.summary_request import SummaryRequest
from app.domain.dtos.summary_response import SummaryResponse
from app.application.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class SummaryService:
    def __init__(self,
                 llm_service: LLMService):
        self.llm_service = llm_service

    async def _ask_llm(self, prompt: str, max_tokens: int) -> str:
        messages = [
            {"role": "system", "content": "Eres un asistente experto en crear resúmenes precisos."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = await self.llm_service.call(messages)

            return response["message"]["content"]

        except Exception as e:
            logger.error(f"Error al llamar al LLM para resumen: {str(e)}")
            raise LLMError(f"Error generando resumen: {str(e)}", code="SUMMARY_LLM_ERROR")

    async def _summarize_chunk(self, chunk: str, max_tokens: int = 150) -> str:
        prompt = f"""
Eres un asistente experto en resumir textos largos.

Dado el siguiente fragmento, produce un resumen claro y breve,
sin perder información importante.

Fragmento:
\"\"\"{chunk}\"\"\"    

Resumen (máximo {max_tokens} tokens):
"""
        return await self._ask_llm(prompt, max_tokens)

    async def _reduce_summaries(self, partial_summaries: List[str], max_tokens: int) -> str:
        joined = "\n---\n".join(partial_summaries)

        prompt = f"""
A continuación tienes múltiples resúmenes parciales de un documento más grande.

Fusiona todos en un único resumen final, coherente, conciso y sin repeticiones.

Resúmenes parciales:
\"\"\"{joined}\"\"\"    

Resumen final (máximo {max_tokens} tokens):
"""
        return await self._ask_llm(prompt, max_tokens)

    async def summarize(self, request: SummaryRequest) -> SummaryResponse:
        chunks = request.chunks
        logger.info(f"Resumiendo documento con {len(chunks)} chunks")

        summaries = await asyncio.gather(
            *[self._summarize_chunk(ch) for ch in chunks]
        )

        final_summary = await self._reduce_summaries(
            summaries, max_tokens=request.target_length
        )

        return SummaryResponse(summary=final_summary)
