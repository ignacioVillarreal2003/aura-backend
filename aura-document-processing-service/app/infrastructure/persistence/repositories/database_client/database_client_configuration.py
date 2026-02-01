import logging
from dataclasses import dataclass
from typing import Final

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class DatabaseClientConfiguration:
    DEFAULT_POOL_SIZE: Final[int] = 10
    DEFAULT_MAX_OVERFLOW: Final[int] = 20
    DEFAULT_POOL_RECYCLE: Final[int] = 3600
    DEFAULT_POOL_PRE_PING: Final[bool] = True
    DEFAULT_ECHO: Final[bool] = False
    DEFAULT_POOL_TIMEOUT: Final[float] = 30.0
    DEFAULT_CONNECT_TIMEOUT: Final[float] = 10.0

    db_driver: str
    db_user: str
    db_password: str
    db_host: str
    db_port: int
    db_name: str
    pool_size: int = DEFAULT_POOL_SIZE
    max_overflow: int = DEFAULT_MAX_OVERFLOW
    pool_recycle: int = DEFAULT_POOL_RECYCLE
    pool_pre_ping: bool = DEFAULT_POOL_PRE_PING
    echo: bool = DEFAULT_ECHO
    pool_timeout: float = DEFAULT_POOL_TIMEOUT
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT

    def __post_init__(
            self
    ) -> None:
        try:
            self._validate_all()
            logger.info("DatabaseClientConfiguration initialized successfully")
        except ValueError as e:
            logger.error(
                "DatabaseClientConfiguration validation failed",
                extra={"error": str(e)},
                exc_info=True
            )
            raise

    def _validate_all(
            self
    ) -> None:
        self._validate_db_driver()
        self._validate_db_user()
        self._validate_db_password()
        self._validate_db_host()
        self._validate_db_port()
        self._validate_db_name()
        self._validate_pool_size()
        self._validate_max_overflow()
        self._validate_pool_recycle()
        self._validate_pool_timeout()
        self._validate_connect_timeout()

    def _validate_db_driver(
            self
    ) -> None:
        if (not self.db_driver
                or not self.db_driver.strip()):
            raise ValueError("db_driver no puede estar vacío")

    def _validate_db_user(
            self
    ) -> None:
        if (not self.db_user
                or not self.db_user.strip()):
            raise ValueError("db_user no puede estar vacío")

    def _validate_db_password(
            self
    ) -> None:
        if not self.db_password:
            raise ValueError("db_password no puede estar vacío")

    def _validate_db_host(
            self
    ) -> None:
        if (not self.db_host
                or not self.db_host.strip()):
            raise ValueError("db_host no puede estar vacío")

    def _validate_db_port(
            self
    ) -> None:
        if not (1
                <= self.db_port
                <= 65535):
            raise ValueError(f"db_port debe estar entre 1 y 65535, se recibió: {self.db_port}")

    def _validate_db_name(
            self
    ) -> None:
        if (not self.db_name
                or not self.db_name.strip()):
            raise ValueError("db_name no puede estar vacío")

    def _validate_pool_size(
            self
    ) -> None:
        if self.pool_size <= 0:
            raise ValueError(f"pool_size debe ser positivo, se recibió: {self.pool_size}")

    def _validate_max_overflow(
            self
    ) -> None:
        if self.max_overflow < 0:
            raise ValueError(f"max_overflow no puede ser negativo, se recibió: {self.max_overflow}")

    def _validate_pool_recycle(
            self
    ) -> None:
        if self.pool_recycle <= 0:
            raise ValueError(f"pool_recycle debe ser positivo, se recibió: {self.pool_recycle}")

    def _validate_pool_timeout(
            self
    ) -> None:
        if self.pool_timeout <= 0:
            raise ValueError(f"pool_timeout debe ser positivo, se recibió: {self.pool_timeout}")

    def _validate_connect_timeout(
            self
    ) -> None:
        if self.connect_timeout <= 0:
            raise ValueError(f"connect_timeout debe ser positivo, se recibió: {self.connect_timeout}")

    def get_database_url(
            self
    ) -> str:
        return (
            f"{self.db_driver}://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )
