from abc import ABC, abstractmethod
from minio import Minio


class MinioClientInterface(ABC):
    @abstractmethod
    async def start(
            self
    ) -> None:
        pass

    @abstractmethod
    async def stop(
            self
    ) -> None:
        pass

    @abstractmethod
    def ensure_bucket(
            self,
            bucket_name: str
    ) -> None:
        pass

    @abstractmethod
    async def health_check(
            self
    ) -> bool:
        pass

    @property
    @abstractmethod
    def is_started(
            self
    ) -> bool:
        pass

    @property
    @abstractmethod
    def client(
            self
    ) -> Minio:
        pass
