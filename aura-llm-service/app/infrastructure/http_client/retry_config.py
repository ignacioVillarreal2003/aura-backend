from typing import Optional

from app.application.exceptions.http_client_exceptions import NetworkError, ExternalServiceError


class RetryConfig:
    def __init__(self,
                 max_attempts: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 10.0,
                 exponential_base: float = 2.0,
                 retry_on_status_codes: Optional[set] = None):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retry_on_status_codes = retry_on_status_codes or {
            408,
            429,
            502,
            503,
            504
        }

    def calculate_delay(self,
                        attempt: int) -> float:
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)

    def should_retry(self,
                     error: Exception,
                     attempt: int) -> bool:
        if attempt >= self.max_attempts:
            return False

        if isinstance(error, NetworkError):
            return True

        if isinstance(error, ExternalServiceError):
            return error.status_code in self.retry_on_status_codes

        return False
