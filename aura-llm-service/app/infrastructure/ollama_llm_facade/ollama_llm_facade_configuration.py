from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class OllamaLLMFacadeConfiguration:
    ollama_model_name: str
    ollama_base_url: str
    ollama_temperature: float = 0.0

    min_ollama_temperature: float = 0.0
    max_ollama_temperature: float = 1.0

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        self._validate_ollama_model_name()
        self._validate_ollama_base_url()
        self._validate_ollama_temperature()

    def _validate_ollama_model_name(self) -> None:
        if not self.ollama_model_name or not self.ollama_model_name.strip():
            raise ValueError(
                f"ollama_model_name cannot be empty or whitespace-only"
            )

    def _validate_ollama_base_url(self) -> None:
        if not self.ollama_base_url or not self.ollama_base_url.strip():
            raise ValueError(
                f"ollama_base_url cannot be empty or whitespace-only"
            )

        try:
            parsed = urlparse(self.ollama_base_url.strip())

            if not parsed.scheme or not parsed.netloc:
                raise ValueError(
                    f"ollama_base_url must be a valid URL with scheme and netloc, got: {self.ollama_base_url}"
                )

            if parsed.scheme not in ("http", "https"):
                raise ValueError(
                    f"ollama_base_url must use http or https scheme, got: {parsed.scheme}"
                )
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(
                f"ollama_base_url is not a valid URL: {self.ollama_base_url}"
            ) from e

    def _validate_ollama_temperature(self) -> None:
        if not isinstance(self.ollama_temperature, (int, float)):
            raise ValueError(
                f"ollama_temperature must be numeric, got {type(self.ollama_temperature).__name__}"
            )

        if not (self.min_ollama_temperature <= self.ollama_temperature <= self.max_ollama_temperature):
            raise ValueError(
                f"ollama_temperature must be between {self.min_ollama_temperature} and {self.max_ollama_temperature}, "
                f"got {self.ollama_temperature}"
            )

    @property
    def normalized_ollama_base_url(self) -> str:
        return self.ollama_base_url.strip().rstrip("/")
