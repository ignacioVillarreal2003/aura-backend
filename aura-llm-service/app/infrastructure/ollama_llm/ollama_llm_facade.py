import logging
from typing import List, Optional
from asyncio import Lock
from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama
from langchain_core.runnables import Runnable

from app.infrastructure.ollama_llm.exceptions.ollama_llm_facade_exceptions import (
    LLMInitializationError,
    LLMNotConfiguredError
)
from app.infrastructure.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.ollama_llm.ollama_llm_facade_configuration import OllamaLLMFacadeConfiguration
from app.infrastructure.ollama_llm.ollama_tool_manager import ToolFactory, OllamaToolManager

logger = logging.getLogger(__name__)


class OllamaLLMFacade(OllamaLLMFacadeInterface):
    def __init__(
            self,
            ollama_llm_facade_configuration: OllamaLLMFacadeConfiguration,
            tool_factories: Optional[List[ToolFactory]] = None
    ) -> None:
        self._ollama_llm_facade_configuration = ollama_llm_facade_configuration

        self._ollama_tool_manager = OllamaToolManager(tool_factories)

        self._initialized = False
        self._init_lock = Lock()

        self._llm_base: Optional[Runnable] = None
        self._llm_with_tools: Optional[Runnable] = None

        logger.info("OllamaLLMFacade initialized successfully")

    @classmethod
    def create(
            cls,
            ollama_model_name: str,
            ollama_base_url: str,
            ollama_temperature: Optional[float] = None,
            tool_factories: Optional[List[ToolFactory]] = None
    ) -> "OllamaLLMFacade":
        config_kwargs = {}

        if ollama_model_name is not None:
            config_kwargs['ollama_model_name'] = ollama_model_name
        if ollama_base_url is not None:
            config_kwargs['ollama_base_url'] = ollama_base_url
        if ollama_temperature is not None:
            config_kwargs['ollama_temperature'] = ollama_temperature

        ollama_llm_facade_configuration = OllamaLLMFacadeConfiguration(**config_kwargs)

        return cls(
            ollama_llm_facade_configuration=ollama_llm_facade_configuration,
            tool_factories=tool_factories
        )

    async def initialize(
            self
    ) -> None:
        async with self._init_lock:
            if self._initialized:
                logger.debug("OllamaLLMFacade already initialized")
                return

            logger.info("Initializing OllamaLLMFacade resources")

            try:
                self._ollama_tool_manager.initialize()
                self._initialize_base_llm()
                self._initialize_llm_with_tools()
                self._initialized = True

                logger.info("OllamaLLMFacade initialized successfully")

            except Exception as e:
                logger.exception(
                    "Unexpected error during OllamaLLMFacade initialization",
                    extra={
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                )
                self._cleanup_on_failure()
                raise LLMInitializationError("Failed to initialize OllamaLLMFacade") from e

    def _initialize_base_llm(
            self
    ) -> None:
        try:
            logger.debug("Initializing base LLM")

            self._llm_base = ChatOllama(
                model=self._ollama_llm_facade_configuration.ollama_model_name,
                base_url=self._ollama_llm_facade_configuration.ollama_base_url,
                temperature=self._ollama_llm_facade_configuration.ollama_temperature,
            )

            logger.info("Base LLM initialized successfully")

        except Exception as e:
            logger.error(
                "Failed to create ChatOllama instance",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise LLMInitializationError(f"Failed to initialize ChatOllama: {str(e)}") from e

    def _initialize_llm_with_tools(
            self
    ) -> None:
        if self._llm_base is None:
            raise LLMInitializationError("Base LLM must be initialized before binding tools")

        if not self._ollama_tool_manager.has_tools:
            logger.debug("No tools to bind, using base LLM")
            self._llm_with_tools = self._llm_base
            return

        try:
            logger.debug("Binding tools to LLM")

            self._llm_with_tools = self._llm_base.bind_tools(
                self._ollama_tool_manager.tools
            )

            logger.info("Tools bound to LLM successfully")

        except Exception as e:
            logger.warning(
                "Failed to bind tools to LLM, falling back to base LLM",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            self._llm_with_tools = self._llm_base

    def _cleanup_on_failure(
            self
    ) -> None:
        logger.debug("Cleaning up after initialization failure")

        self._initialized = False
        self._llm_base = None
        self._llm_with_tools = None

    async def _ensure_initialized(
            self
    ) -> None:
        if self._initialized:
            return

        logger.debug("Lazy-initializing OllamaLLMFacade on first use")

        try:
            await self.initialize()
        except LLMInitializationError:
            raise
        except Exception as e:
            logger.error(
                "Failed to lazy-initialize OllamaLLMFacade",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise LLMNotConfiguredError("Failed to initialize OllamaLLMFacade") from e

    async def get_llm_base(
            self
    ) -> Runnable:
        await self._ensure_initialized()

        if self._llm_base is None:
            logger.error("Base LLM is not configured after initialization")
            raise LLMNotConfiguredError("Base LLM is not configured")

        return self._llm_base

    async def get_llm_with_tools(
            self
    ) -> Runnable:
        await self._ensure_initialized()

        if self._llm_with_tools is None:
            logger.error("LLM with tools is not configured after initialization")
            raise LLMNotConfiguredError("LLM with tools is not configured")

        return self._llm_with_tools

    @property
    def tools(
            self
    ) -> List[BaseTool]:
        return self._ollama_tool_manager.tools

    @property
    def tool_instructions(
            self
    ) -> Optional[str]:
        return self._ollama_tool_manager.generate_instructions()
