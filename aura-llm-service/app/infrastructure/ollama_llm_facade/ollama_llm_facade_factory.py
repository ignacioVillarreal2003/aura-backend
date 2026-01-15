import logging
from typing import Optional, List
from asyncio import Lock

from app.infrastructure.ollama_llm_facade.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.ollama_llm_facade.ollama_llm_facade import OllamaLLMFacade
from app.infrastructure.ollama_llm_facade.ollama_tool_manager import ToolFactory

logger = logging.getLogger(__name__)

_global_ollama_llm_facade: Optional[OllamaLLMFacadeInterface] = None
_global_ollama_llm_facade_lock = Lock()


async def get_global_ollama_llm_facade(*,
                                       ollama_model_name: str,
                                       ollama_base_url: str,
                                       ollama_temperature: Optional[float] = None,
                                       tool_factories: Optional[List[ToolFactory]] = None,
                                       auto_initialize: bool = True) -> OllamaLLMFacadeInterface:
    global _global_ollama_llm_facade

    async with _global_ollama_llm_facade_lock:
        if _global_ollama_llm_facade is None:
            logger.info("Creating global OllamaLLMFacade singleton")

            _global_ollama_llm_facade = OllamaLLMFacade.create(
                ollama_model_name=ollama_model_name,
                ollama_base_url=ollama_base_url,
                ollama_temperature=ollama_temperature,
                tool_factories=tool_factories
            )

            if auto_initialize:
                await _global_ollama_llm_facade.initialize()
                logger.info("Global OllamaLLMFacade initialized successfully")

        else:
            logger.debug("Returning existing global OllamaLLMFacade")

    return _global_ollama_llm_facade


async def shutdown_global_ollama_llm_facade() -> None:
    global _global_ollama_llm_facade

    async with _global_ollama_llm_facade_lock:
        if _global_ollama_llm_facade is not None:
            logger.info("Shutting down global OllamaLLMFacade")
            _global_ollama_llm_facade = None
            logger.info("Global OllamaLLMFacade shut down successfully")
        else:
            logger.debug("Global OllamaLLMFacade already shut down")
