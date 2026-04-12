import logging
from asyncio import Lock
from typing import List, Optional
from fastapi import HTTPException, Request, status
from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama

from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_facade_exceptions import (
    LLMInitializationError,
    LLMNotConfiguredError
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.ollama_llm_facade_settings import OllamaLLMFacadeSettings
from app.infrastructure.llm.ollama_llm.ollama_tool_manager import (
    OllamaToolManager,
    ToolFactory
)

logger = logging.getLogger(__name__)


class OllamaLLMFacade(OllamaLLMFacadeInterface):
    def __init__(
            self,
            ollama_llm_facade_settings: Optional[OllamaLLMFacadeSettings] = None,
            tool_factories: Optional[List[ToolFactory]] = None
    ) -> None:
        self._settings = ollama_llm_facade_settings or OllamaLLMFacadeSettings()
        self._tool_manager = OllamaToolManager(tool_factories)

        self._initialized: bool = False
        self._init_failed: bool = False
        self._init_lock: Lock = Lock()

        self._llm_base: Optional[Runnable] = None
        self._llm_with_tools: Optional[Runnable] = None

        logger.info("OllamaLLMFacade created")

    async def initialize(self) -> None:
        async with self._init_lock:
            if self._initialized:
                logger.debug("OllamaLLMFacade already initialized")
                return

            logger.info(
                "Initializing OllamaLLMFacade",
                extra={
                    "model_name": self._settings.model_name,
                    "base_url": self._settings.base_url
                }
            )

            try:
                self._tool_manager.initialize()
                self._build_base_llm()
                self._bind_tools()
                await self._probe_connectivity()
                self._initialized = True

                logger.info("OllamaLLMFacade initialized successfully")

            except Exception as e:
                logger.exception(
                    "Failed to initialize OllamaLLMFacade",
                    extra={"error_type": type(e).__name__, "error_message": str(e)}
                )
                self._cleanup_on_failure()
                raise LLMInitializationError("Failed to initialize OllamaLLMFacade") from e

    async def get_llm_base(self) -> Runnable:
        await self._ensure_initialized()
        if self._llm_base is None:
            raise LLMNotConfiguredError("Base LLM is not configured")
        return self._llm_base

    async def get_llm_with_tools(self) -> Runnable:
        await self._ensure_initialized()
        if self._llm_with_tools is None:
            raise LLMNotConfiguredError("LLM with tools is not configured")
        return self._llm_with_tools

    @property
    def tools(self) -> List[BaseTool]:
        return self._tool_manager.tools

    @property
    def tool_instructions(self) -> Optional[str]:
        return self._tool_manager.generate_instructions()

    def _build_base_llm(self) -> None:
        try:
            logger.debug("Building base LLM")
            self._llm_base = ChatOllama(**self._settings.get_chat_ollama_kwargs())
            logger.info("Base LLM built successfully")
        except Exception as e:
            raise LLMInitializationError(f"Failed to build ChatOllama: {e}") from e

    def _bind_tools(self) -> None:
        if self._llm_base is None:
            raise LLMInitializationError("Base LLM must be built before binding tools")

        if not self._tool_manager.has_tools:
            logger.debug("No tools to bind — using base LLM as-is")
            self._llm_with_tools = self._llm_base
            return

        try:
            logger.debug("Binding tools to LLM")
            self._llm_with_tools = self._llm_base.bind_tools(self._tool_manager.tools)
            logger.info(
                "Tools bound to LLM successfully",
                extra={"tool_count": len(self._tool_manager.tools)}
            )
        except Exception as e:
            logger.warning(
                "Failed to bind tools — falling back to base LLM",
                extra={"error_type": type(e).__name__, "error_message": str(e)},
                exc_info=True
            )
            self._llm_with_tools = self._llm_base

    async def _probe_connectivity(self) -> None:
        if self._llm_base is None:
            raise LLMInitializationError("Base LLM must be built before probing connectivity")

        try:
            logger.debug("Probing Ollama connectivity")
            await self._llm_base.ainvoke([HumanMessage(content="hi")])
            logger.info("Ollama connectivity probe successful")
        except Exception as e:
            raise LLMInitializationError(
                f"Ollama connectivity probe failed — is the server running "
                f"and model '{self._settings.model_name}' loaded? Error: {e}"
            ) from e

    def _cleanup_on_failure(self) -> None:
        self._initialized = False
        self._init_failed = True
        self._llm_base = None
        self._llm_with_tools = None

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        if self._init_failed:
            raise LLMNotConfiguredError(
                "OllamaLLMFacade failed to initialize and will not retry. "
                "Restart the application to try again."
            )

        logger.debug("Lazy-initializing OllamaLLMFacade on first use")
        try:
            await self.initialize()
        except LLMInitializationError:
            raise
        except Exception as e:
            logger.exception("Unexpected failure during lazy initialization")
            raise LLMNotConfiguredError("Failed to initialize OllamaLLMFacade") from e


async def get_ollama_llm_facade_base(request: Request) -> OllamaLLMFacadeInterface:
    try:
        return request.app.state.ollama_llm_facade_base
    except AttributeError:
        logger.error("OllamaLLMFacade base not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service (base) is not available",
        )


async def get_ollama_llm_facade_with_tools(request: Request) -> OllamaLLMFacadeInterface:
    try:
        return request.app.state.ollama_llm_facade_with_tools
    except AttributeError:
        logger.error("OllamaLLMFacade with tools not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service (with tools) is not available",
        )
