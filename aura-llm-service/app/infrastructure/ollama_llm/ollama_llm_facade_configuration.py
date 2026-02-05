import logging
from dataclasses import dataclass
from typing import Final, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass(
    frozen=True,
    kw_only=True
)
class OllamaLLMFacadeConfiguration:
    OLLAMA_TEMPERATURE: Final[Tuple[float, float]] = (0.0, 1.0)

    DEFAULT_OLLAMA_TEMPERATURE: Final[float] = 0.0

    ollama_model_name: str
    ollama_base_url: str
    ollama_temperature: float = DEFAULT_OLLAMA_TEMPERATURE

    def __post_init__(
            self
    ) -> None:
        try:
            self._validate_all()
            logger.info("OllamaLLMFacadeConfiguration initialized successfully")
        except ValueError as e:
            logger.error(
                "OllamaLLMFacadeConfiguration validation failed",
                extra={
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    def _validate_all(
            self
    ) -> None:
        self._validate_ollama_model_name()
        self._validate_ollama_base_url()
        self._validate_ollama_temperature()

    def _validate_ollama_model_name(
            self
    ) -> None:
        if not self.ollama_model_name or not self.ollama_model_name.strip():
            raise ValueError("ollama_model_name no puede estar vacío ni contener solo espacios en blanco")

    def _validate_ollama_base_url(
            self
    ) -> None:
        if not self.ollama_base_url or not self.ollama_base_url.strip():
            raise ValueError("ollama_base_url no puede estar vacío ni contener solo espacios en blanco")

        try:
            parsed = urlparse(self.ollama_base_url.strip())

            if not parsed.scheme or not parsed.netloc:
                raise ValueError("ollama_base_url debe ser una URL válida con esquema y host")

            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"ollama_base_url debe usar el esquema http o https, se recibió: {parsed.scheme}")

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"ollama_base_url no es una URL válida: {self.ollama_base_url}") from e

    def _validate_ollama_temperature(
            self
    ) -> None:
        if not (self.OLLAMA_TEMPERATURE[0]
                <= self.ollama_temperature
                <= self.OLLAMA_TEMPERATURE[1]):
            raise ValueError(
                f"ollama_temperature debe estar entre {self.OLLAMA_TEMPERATURE[0]} y {self.OLLAMA_TEMPERATURE[1]}, "
                f"se recibió: {self.ollama_temperature}"
            )
