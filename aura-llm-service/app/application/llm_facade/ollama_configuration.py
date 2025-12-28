from dataclasses import dataclass
from urllib.parse import urlparse

from app.application.exceptions.app_exceptions import ValidationError


@dataclass(frozen=True)
class OllamaConfiguration:
    model_name: str
    base_url: str
    temperature: float = 0.0

    MIN_TEMPERATURE: float = 0.0
    MAX_TEMPERATURE: float = 1.0

    def __post_init__(self):
        self._validate()

    def _validate(self) -> None:
        self._validate_model_name()
        self._validate_base_url()
        self._validate_temperature()

    def _validate_model_name(self) -> None:
        if not self.model_name or not self.model_name.strip():
            raise ValidationError(
                "ollama_model_name cannot be empty",
                status_code=400
            )

    def _validate_base_url(self) -> None:
        if not self.base_url or not self.base_url.strip():
            raise ValidationError(
                "ollama_base_url cannot be empty",
                status_code=400
            )

        try:
            parsed = urlparse(self.base_url.strip())

            if not parsed.scheme or not parsed.netloc:
                raise ValidationError(
                    "ollama_base_url must be a valid URL",
                    status_code=400
                )

            if parsed.scheme not in ("http", "https"):
                raise ValidationError(
                    "ollama_base_url must use http or https scheme",
                    status_code=400
                )
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(
                "ollama_base_url is not a valid URL",
                status_code=400
            ) from e

    def _validate_temperature(self) -> None:
        if not isinstance(self.temperature, (int, float)):
            raise ValidationError(
                "ollama_temperature must be numeric",
                status_code=400
            )

        if not (self.MIN_TEMPERATURE <= self.temperature <= self.MAX_TEMPERATURE):
            raise ValidationError(
                f"ollama_temperature must be between {self.MIN_TEMPERATURE} "
                f"and {self.MAX_TEMPERATURE}",
                status_code=400
            )

    @property
    def normalized_base_url(self) -> str:
        return self.base_url.strip().rstrip("/")
