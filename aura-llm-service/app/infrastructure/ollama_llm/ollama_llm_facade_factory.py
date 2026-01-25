import logging
from typing import Optional, List
from asyncio import Lock

from app.infrastructure.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.ollama_llm.ollama_llm_facade import OllamaLLMFacade
from app.infrastructure.ollama_llm.ollama_tool_manager import ToolFactory

logger = logging.getLogger(__name__)

_global_ollama_llm_facade_base: Optional[OllamaLLMFacadeInterface] = None
_global_ollama_llm_facade_base_lock = Lock()

_global_ollama_llm_facade_with_tools: Optional[OllamaLLMFacadeInterface] = None
_global_ollama_llm_facade_with_tools_lock = Lock()


async def get_global_ollama_llm_facade_base(ollama_model_name: str,
                                            ollama_base_url: str,
                                            ollama_temperature: Optional[float] = None) -> OllamaLLMFacadeInterface:
    global _global_ollama_llm_facade_base

    async with _global_ollama_llm_facade_base_lock:
        if _global_ollama_llm_facade_base is None:
            logger.info("Creating global OllamaLLMFacade base singleton")

            _global_ollama_llm_facade_base = OllamaLLMFacade.create(
                ollama_model_name=ollama_model_name,
                ollama_base_url=ollama_base_url,
                ollama_temperature=ollama_temperature,
                tool_factories=None
            )

            await _global_ollama_llm_facade_base.initialize()
            logger.info("Global OllamaLLMFacade base initialized successfully")

        else:
            logger.debug("Returning existing global OllamaLLMFacade base")

    return _global_ollama_llm_facade_base


async def get_global_ollama_llm_facade_with_tools(ollama_model_name: str,
                                                  ollama_base_url: str,
                                                  tool_factories: List[ToolFactory],
                                                  ollama_temperature: Optional[float] = None) -> OllamaLLMFacadeInterface:
    global _global_ollama_llm_facade_with_tools

    async with _global_ollama_llm_facade_with_tools_lock:
        if _global_ollama_llm_facade_with_tools is None:
            logger.info("Creating global OllamaLLMFacade with tools singleton")

            _global_ollama_llm_facade_with_tools = OllamaLLMFacade.create(
                ollama_model_name=ollama_model_name,
                ollama_base_url=ollama_base_url,
                ollama_temperature=ollama_temperature,
                tool_factories=tool_factories
            )

            await _global_ollama_llm_facade_with_tools.initialize()
            logger.info("Global OllamaLLMFacade with tools initialized successfully")

        else:
            logger.debug("Returning existing global OllamaLLMFacade with tools")

    return _global_ollama_llm_facade_with_tools


async def shutdown_global_ollama_llm_facades() -> None:
    global _global_ollama_llm_facade_base, _global_ollama_llm_facade_with_tools

    async with _global_ollama_llm_facade_base_lock:
        if _global_ollama_llm_facade_base is not None:
            logger.info("Shutting down global OllamaLLMFacade base")
            _global_ollama_llm_facade_base = None
            logger.info("Global OllamaLLMFacade base shut down successfully")

    async with _global_ollama_llm_facade_with_tools_lock:
        if _global_ollama_llm_facade_with_tools is not None:
            logger.info("Shutting down global OllamaLLMFacade with tools")
            _global_ollama_llm_facade_with_tools = None
            logger.info("Global OllamaLLMFacade with tools shut down successfully")
