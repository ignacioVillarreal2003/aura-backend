import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.infrastructure.guardrails.nemo_guardrails_settings import NemoGuardrailsSettings
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "nemo_config"


@dataclass(frozen=True)
class GuardrailsVerdict:
    allowed: bool
    reason: Optional[str] = None


class NemoGuardrailsService:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            settings: Optional[NemoGuardrailsSettings] = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._settings = settings or NemoGuardrailsSettings()
        self._rails: Optional[Any] = None
        self._init_lock = asyncio.Lock()
        self._unavailable = False
        logger.info(
            "NemoGuardrailsService initialized",
            extra={"enabled": self._settings.enabled, "fail_open": self._settings.fail_open},
        )

    @property
    def is_active(self) -> bool:
        return self._settings.enabled and not self._unavailable

    @property
    def settings(self) -> NemoGuardrailsSettings:
        return self._settings

    async def warmup(self) -> None:
        if not self.is_active:
            return
        try:
            await self._ensure_rails()
        except Exception:
            logger.warning(
                "Guardrails warmup failed; rails will initialize on first use.",
                exc_info=True,
            )

    async def check_input(self, text: str) -> GuardrailsVerdict:
        if not self.is_active or not text or not text.strip():
            return GuardrailsVerdict(allowed=True)

        try:
            rails = await self._ensure_rails()
            if rails is None:
                return GuardrailsVerdict(allowed=True)
            return await self._run_input_rails(rails, text)
        except Exception:
            if self._settings.fail_open:
                logger.warning(
                    "Guardrails check failed; allowing request (fail-open).",
                    exc_info=True,
                )
                return GuardrailsVerdict(allowed=True)
            raise

    async def check_output(self, text: str) -> GuardrailsVerdict:
        if not self._settings.check_output or not self.is_active or not text or not text.strip():
            return GuardrailsVerdict(allowed=True)

        try:
            rails = await self._ensure_rails()
            if rails is None:
                return GuardrailsVerdict(allowed=True)
            return await self._run_output_rails(rails, text)
        except Exception:
            if self._settings.fail_open:
                logger.warning(
                    "Guardrails output check failed; allowing response (fail-open).",
                    exc_info=True,
                )
                return GuardrailsVerdict(allowed=True)
            raise

    async def _run_input_rails(self, rails: Any, text: str) -> GuardrailsVerdict:
        from nemoguardrails.rails.llm.options import GenerationOptions

        truncated = text[: self._settings.max_input_chars]
        options = GenerationOptions(rails=["input"], log={"activated_rails": True})
        result = await asyncio.wait_for(
            rails.generate_async(
                messages=[{"role": "user", "content": truncated}],
                options=options,
            ),
            timeout=self._settings.check_timeout_seconds,
        )

        activated = (result.log.activated_rails or []) if result.log else []
        stopped = [rail for rail in activated if getattr(rail, "stop", False)]
        if stopped:
            reason = stopped[0].name or "input rail"
            logger.warning(
                "Guardrails blocked user input.",
                extra={"rail": reason, "input_preview": truncated[:200]},
            )
            return GuardrailsVerdict(allowed=False, reason=reason)
        return GuardrailsVerdict(allowed=True)

    async def _run_output_rails(self, rails: Any, text: str) -> GuardrailsVerdict:
        from nemoguardrails.rails.llm.options import GenerationOptions

        truncated = text[: self._settings.max_output_chars]
        options = GenerationOptions(rails=["output"], log={"activated_rails": True})
        result = await asyncio.wait_for(
            rails.generate_async(
                messages=[
                    {"role": "user", "content": ""},
                    {"role": "assistant", "content": truncated},
                ],
                options=options,
            ),
            timeout=self._settings.check_timeout_seconds,
        )

        activated = (result.log.activated_rails or []) if result.log else []
        stopped = [rail for rail in activated if getattr(rail, "stop", False)]
        if stopped:
            reason = stopped[0].name or "output rail"
            logger.warning(
                "Guardrails blocked LLM output.",
                extra={"rail": reason},
            )
            return GuardrailsVerdict(allowed=False, reason=reason)
        return GuardrailsVerdict(allowed=True)

    async def _ensure_rails(self) -> Optional[Any]:
        if self._rails is not None or self._unavailable:
            return self._rails
        async with self._init_lock:
            if self._rails is not None or self._unavailable:
                return self._rails
            try:
                from nemoguardrails import LLMRails, RailsConfig
            except ImportError:
                self._unavailable = True
                logger.warning(
                    "nemoguardrails is not installed; the input filter is disabled. "
                    "Install requirements/requirements.txt to enable it."
                )
                return None

            llm = await self._ollama_llm_facade.get_llm_base()
            llm = llm.bind(reasoning=False, num_predict=8, temperature=0.0)
            try:
                from nemoguardrails.integrations.langchain.llm_adapter import LangChainLLMAdapter

                llm = LangChainLLMAdapter(llm)
            except ImportError:
                pass

            config = RailsConfig.from_path(str(_CONFIG_PATH))
            self._rails = await asyncio.to_thread(
                lambda: LLMRails(config=config, llm=llm, verbose=False)
            )
            logger.info("NeMo Guardrails input rails initialized.")
            return self._rails
