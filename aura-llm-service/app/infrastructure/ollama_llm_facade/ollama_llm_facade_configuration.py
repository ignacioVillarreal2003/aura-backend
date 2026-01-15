import logging
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass(
    frozen=True,
    kw_only=True
)
class OllamaLLMFacadeConfiguration:
    MIN_OLLAMA_TEMPERATURE: Final[float] = 0.0
    MAX_OLLAMA_TEMPERATURE: Final[float] = 1.0

    DEFAULT_OLLAMA_TEMPERATURE: Final[float] = 0.0

    ollama_model_name: str
    ollama_base_url: str
    ollama_temperature: float = DEFAULT_OLLAMA_TEMPERATURE

    def __post_init__(self) -> None:
        try:
            self._validate_all()
            logger.info(
                "OllamaLLMFacadeConfiguration initialized successfully",
                extra={
                    "ollama_model_name": self.ollama_model_name,
                    "ollama_base_url": self.normalized_ollama_base_url,
                    "ollama_temperature": self.ollama_temperature
                }
            )
        except ValueError as e:
            logger.error(
                "OllamaLLMFacadeConfiguration validation failed",
                extra={
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    def _validate_all(self) -> None:
        self._validate_ollama_model_name()
        self._validate_ollama_base_url()
        self._validate_ollama_temperature()

    def _validate_ollama_model_name(self) -> None:
        if not self.ollama_model_name or not self.ollama_model_name.strip():
            raise ValueError(
                "ollama_model_name no puede estar vacío ni contener solo espacios en blanco"
            )

    def _validate_ollama_base_url(self) -> None:
        if not self.ollama_base_url or not self.ollama_base_url.strip():
            raise ValueError(
                "ollama_base_url no puede estar vacío ni contener solo espacios en blanco"
            )

        try:
            parsed = urlparse(self.ollama_base_url.strip())

            if not parsed.scheme or not parsed.netloc:
                raise ValueError(
                    "ollama_base_url debe ser una URL válida con esquema y host"
                )

            if parsed.scheme not in ("http", "https"):
                raise ValueError(
                    f"ollama_base_url debe usar el esquema http o https, se recibió: {parsed.scheme}"
                )

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(
                f"ollama_base_url no es una URL válida: {self.ollama_base_url}"
            ) from e

    def _validate_ollama_temperature(self) -> None:
        if not isinstance(self.ollama_temperature, (int, float)):
            raise ValueError(
                f"ollama_temperature debe ser numérico, se recibió: {type(self.ollama_temperature).__name__}"
            )

        if not (self.MIN_OLLAMA_TEMPERATURE
            <= self.ollama_temperature
            <= self.MAX_OLLAMA_TEMPERATURE):
            raise ValueError(
                f"ollama_temperature debe estar entre {self.MIN_OLLAMA_TEMPERATURE} y {self.MAX_OLLAMA_TEMPERATURE}, "
                f"se recibió: {self.ollama_temperature}"
            )

    @property
    def normalized_ollama_base_url(self) -> str:
        return self.ollama_base_url.strip().rstrip("/")
