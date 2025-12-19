import logging
import asyncio

from app.application.exceptions.app_exceptions import LLMError
from app.application.services.llm_service import LLMService
from app.domain.dtos.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary_response import DocumentSummaryResponse

logger = logging.getLogger(__name__)


class SummaryService:
    def __init__(self,
                 llm_service: LLMService):
        self.llm_service = llm_service

    async def _ask_llm(self, prompt: str) -> str:
        messages = [
            {"role": "system", "content": "Eres un asistente experto en crear resúmenes precisos."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = await self.llm_service.call(messages)

            return response["message"]["content"]

        except Exception as e:
            logger.error(f"Error calling LLM for summary: {str(e)}", extra={"error": str(e)})
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
        return await self._ask_llm(prompt)

    async def _reduce_summaries(self, partial_summaries: list[str], max_tokens: int) -> str:
        joined = "\n---\n".join(partial_summaries)

        prompt = f"""
        A continuación tienes múltiples resúmenes parciales de un documento más grande.
        
        Fusiona todos en un único resumen final, coherente, conciso y sin repeticiones.
        
        Resúmenes parciales:
        \"\"\"{joined}\"\"\"    
        
        Resumen final (máximo {max_tokens} tokens):
        """
        return await self._ask_llm(prompt)

    async def summarize(self, request: DocumentSummaryRequest) -> DocumentSummaryResponse:
        chunks = request.fragments
        logger.info(f"Summarizing document with {len(chunks)} chunks", extra={"chunk_count": len(chunks)})

        semaphore = asyncio.Semaphore(2)

        async def summarize_with_limit(chunk: str):
            async with semaphore:
                for attempt in range(3):
                    try:
                        return await self._summarize_chunk(chunk)
                    except Exception as e:
                        if attempt == 2:
                            raise
                        await asyncio.sleep(2)

        summaries = await asyncio.gather(
            *[summarize_with_limit(ch) for ch in chunks],
            return_exceptions=True
        )

        successful_summaries = []
        for i, summary in enumerate(summaries):
            if isinstance(summary, Exception):
                logger.warning(f"Error summarizing chunk {i}: {summary}", extra={"chunk_index": i, "error": str(summary)})
                successful_summaries.append(f"[Summary failed: {chunks[i][:100]}...]")
            else:
                successful_summaries.append(summary)

        final_summary = await self._reduce_summaries(
            successful_summaries, max_tokens=600
        )

        return DocumentSummaryResponse(summary=final_summary)
