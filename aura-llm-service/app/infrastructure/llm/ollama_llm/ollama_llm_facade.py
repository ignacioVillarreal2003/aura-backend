import enum
import logging
import time
from asyncio import Lock
from typing import Any, List, Optional
import httpx
from fastapi import HTTPException, Request, status
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama

from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_facade_exceptions import (
    LLMInitializationError,
    LLMNotConfiguredError,
    OllamaLLMFacadeError,
    ToolInitializationError,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.ollama_llm_facade_settings import OllamaLLMFacadeSettings
from app.infrastructure.llm.ollama_llm.ollama_tool_manager import OllamaToolManager, ToolFactory

logger = logging.getLogger(__name__)

_PROBE_TIMEOUT: float = 10.0
_RUNTIME_PROBE_TIMEOUT: float = 1.5


_OLLAMA_OPTION_KEYS = frozenset({
    "temperature", "top_p", "top_k", "seed", "repeat_penalty", "repeat_last_n",
    "num_ctx", "num_predict", "num_gpu", "num_thread",
    "mirostat", "mirostat_eta", "mirostat_tau", "tfs_z",
})

_OLLAMA_OPTION_ALIASES = {
    "max_tokens": "num_predict",
    "max_output_tokens": "num_predict",
}


class _ChatOllamaWithCallTimeOptions(ChatOllama):
    def _chat_params(
            self,
            messages: Any,
            stop: Optional[List[str]] = None,
            **kwargs: Any,
    ) -> dict:
        overrides = {
            key: kwargs.pop(key)
            for key in list(kwargs)
            if key in _OLLAMA_OPTION_KEYS
        }
        for alias, option_key in _OLLAMA_OPTION_ALIASES.items():
            if alias in kwargs:
                overrides.setdefault(option_key, kwargs.pop(alias))
        params = super()._chat_params(messages, stop=stop, **kwargs)
        if overrides:
            params["options"].update(overrides)
        return params


class _CircuitState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


def _model_is_available(model_name: str, available_names: set[str]) -> bool:
    if model_name in available_names:
        return True
    if ":" not in model_name and f"{model_name}:latest" in available_names:
        return True
    if model_name.endswith(":latest") and model_name[: -len(":latest")] in available_names:
        return True
    return False


class OllamaLLMFacade(OllamaLLMFacadeInterface):
    def __init__(
            self,
            ollama_llm_facade_settings: Optional[OllamaLLMFacadeSettings] = None,
            tool_factories: Optional[List[ToolFactory]] = None,
    ) -> None:
        self._settings = ollama_llm_facade_settings or OllamaLLMFacadeSettings()
        self._tool_manager = OllamaToolManager(tool_factories)

        self._initialized: bool = False
        self._circuit_state: _CircuitState = _CircuitState.CLOSED
        self._consecutive_failures: int = 0
        self._opened_at: float = 0.0
        self._tools_bound: bool = False
        self._init_lock: Lock = Lock()

        self._llm_base: Optional[Runnable] = None
        self._llm_json: Optional[Runnable] = None
        self._llm_with_tools: Optional[Runnable] = None

        self._probe_client: Optional[httpx.AsyncClient] = None

        logger.info("OllamaLLMFacade created")

    def _get_probe_client(self) -> httpx.AsyncClient:
        if self._probe_client is None:
            self._probe_client = httpx.AsyncClient()
        return self._probe_client

    async def aclose(self) -> None:
        if self._probe_client is not None:
            try:
                await self._probe_client.aclose()
            except Exception:
                logger.warning("Failed to close the Ollama probe client.", exc_info=True)
            finally:
                self._probe_client = None

    async def initialize(self) -> None:
        async with self._init_lock:
            if self._initialized:
                logger.debug("OllamaLLMFacade already initialized.")
                return

            match self._circuit_state:
                case _CircuitState.OPEN:
                    elapsed = time.monotonic() - self._opened_at
                    cooldown = self._settings.circuit_recovery_cooldown_seconds
                    if elapsed < cooldown:
                        remaining = cooldown - elapsed
                        raise LLMNotConfiguredError(
                            f"OllamaLLMFacade circuit is open — initialization failed. "
                            f"Recovery attempt in {remaining:.0f}s."
                        )
                    logger.info("Circuit transitioning to HALF_OPEN — retrying initialization.")
                    self._circuit_state = _CircuitState.HALF_OPEN
                case _CircuitState.HALF_OPEN | _CircuitState.CLOSED:
                    pass

            logger.info(
                "Initializing OllamaLLMFacade",
                extra={
                    "model_name": self._settings.model_name,
                    "base_url": self._settings.base_url,
                    "circuit_state": self._circuit_state.value,
                },
            )

            try:
                self._tool_manager.initialize()
                self._build_base_llm()
                self._bind_tools()
                await self._probe_connectivity()
                self._initialized = True
                self._circuit_state = _CircuitState.CLOSED
                self._consecutive_failures = 0
                logger.info("OllamaLLMFacade initialized successfully")

            except OllamaLLMFacadeError:
                logger.exception("OllamaLLMFacade initialization failed.")
                self._cleanup_on_failure()
                raise

            except Exception as e:
                logger.exception(
                    "Unexpected error during OllamaLLMFacade initialization",
                    extra={"error_type": type(e).__name__},
                )
                self._cleanup_on_failure()
                raise LLMInitializationError(
                    "Unexpected error during OllamaLLMFacade initialization."
                ) from e

    async def get_llm_base(self) -> Runnable:
        await self._ensure_initialized()
        if self._llm_base is None:
            raise LLMNotConfiguredError("Base LLM is not configured.")
        return self._llm_base

    async def get_llm_json(self) -> Runnable:
        await self._ensure_initialized()
        if self._llm_json is None:
            raise LLMNotConfiguredError("JSON-mode LLM is not configured.")
        return self._llm_json

    async def get_llm_with_tools(self) -> Runnable:
        await self._ensure_initialized()
        if self._llm_with_tools is None:
            raise LLMNotConfiguredError("LLM with tools is not configured.")
        return self._llm_with_tools

    def is_healthy(self) -> bool:
        return self._initialized and self._circuit_state == _CircuitState.CLOSED

    async def check_health(self) -> bool:
        if not self._initialized or self._circuit_state != _CircuitState.CLOSED:
            return False
        try:
            client = self._get_probe_client()
            response = await client.get(
                f"{self._settings.base_url}/api/tags",
                timeout=_RUNTIME_PROBE_TIMEOUT,
            )
            response.raise_for_status()
            return True
        except Exception:
            logger.warning("Ollama runtime health probe failed.", exc_info=True)
            return False

    @property
    def tools_bound(self) -> bool:
        return self._tools_bound

    def register_tools(self, tool_factories: List[ToolFactory]) -> None:
        if not self._initialized:
            raise LLMNotConfiguredError("Facade must be initialized before registering tools.")
        logger.info("Registering tools", extra={"tool_factory_count": len(tool_factories)})
        self._tool_manager = OllamaToolManager(tool_factories)
        self._tool_manager.initialize()
        bound = self._bind_tools()
        if self._tool_manager.has_tools and not bound:
            raise ToolInitializationError(
                "Tools were created but could not be bound to the LLM — "
                "check that the model supports tool calling."
            )
        if bound:
            logger.info(
                "Tools registered and bound successfully",
                extra={"tool_count": len(self._tool_manager.tools)},
            )
        else:
            logger.debug("No tools provided — skipping tool binding.")

    @property
    def tools(self) -> List[BaseTool]:
        return self._tool_manager.tools

    @property
    def tool_instructions(self) -> Optional[str]:
        return self._tool_manager.generate_instructions()

    def _build_base_llm(self) -> None:
        try:
            logger.debug("Building base LLM")
            kwargs = self._settings.get_chat_ollama_kwargs()
            self._llm_base = _ChatOllamaWithCallTimeOptions(**kwargs)
            self._llm_json = _ChatOllamaWithCallTimeOptions(**kwargs, format="json")
            logger.info("Base LLM built successfully")
        except Exception as e:
            raise LLMInitializationError(f"Failed to build ChatOllama: {e}") from e

    def _bind_tools(self) -> bool:
        if self._llm_base is None:
            raise LLMInitializationError("Base LLM must be built before binding tools.")

        if not self._tool_manager.has_tools:
            logger.debug("No tools to bind — using base LLM as-is.")
            self._llm_with_tools = self._llm_base
            self._tools_bound = False
            return False

        try:
            logger.debug("Binding tools to LLM")
            self._llm_with_tools = self._llm_base.bind_tools(self._tool_manager.tools)
            self._tools_bound = True
            logger.info(
                "Tools bound to LLM successfully",
                extra={"tool_count": len(self._tool_manager.tools)},
            )
            return True
        except Exception as e:
            logger.warning(
                "Failed to bind tools — falling back to base LLM",
                extra={"error_type": type(e).__name__, "error_message": str(e)},
                exc_info=True,
            )
            self._llm_with_tools = self._llm_base
            self._tools_bound = False
            return False

    async def _probe_connectivity(self) -> None:
        tags_url = f"{self._settings.base_url}/api/tags"
        logger.debug("Probing Ollama connectivity", extra={"url": tags_url})

        try:
            client = self._get_probe_client()
            response = await client.get(tags_url, timeout=_PROBE_TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except OllamaLLMFacadeError:
            raise
        except Exception as e:
            raise LLMInitializationError(
                f"Ollama connectivity probe failed at '{tags_url}' — "
                f"is the server running? Error: {e}"
            ) from e

        models = data.get("models", [])
        available_names: set[str] = {
            m.get("name", "")
            for m in models
            if isinstance(m, dict) and m.get("name")
        }

        model_name = self._settings.model_name
        if not _model_is_available(model_name, available_names):
            raise LLMInitializationError(
                f"Model '{model_name}' is not available in Ollama. "
                f"Pull it with: 'ollama pull {model_name}'. "
                f"Available models: {sorted(available_names) or ['none']}."
            )

        logger.info(
            "Ollama connectivity probe successful — model is available",
            extra={"model_name": model_name},
        )

    def _cleanup_on_failure(self) -> None:
        self._initialized = False
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._settings.circuit_failure_threshold:
            self._circuit_state = _CircuitState.OPEN
            self._opened_at = time.monotonic()
            logger.warning(
                "Circuit opened after initialization failure",
                extra={
                    "consecutive_failures": self._consecutive_failures,
                    "recovery_in_seconds": self._settings.circuit_recovery_cooldown_seconds,
                },
            )
        self._tools_bound = False
        self._llm_base = None
        self._llm_json = None
        self._llm_with_tools = None

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        await self.initialize()


async def get_ollama_llm_facade(request: Request) -> OllamaLLMFacadeInterface:
    try:
        return request.app.state.ollama_llm_facade
    except AttributeError as e:
        logger.error("OllamaLLMFacade not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service is not available",
        ) from e
