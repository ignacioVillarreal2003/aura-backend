from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Optional
from minio import Minio


class MinioManagerInterface(ABC):
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

    @abstractmethod
    async def ensure_bucket(
            self,
            bucket_name: str
    ) -> None:
        pass

    @abstractmethod
    async def upload_file(
            self,
            bucket_name: str,
            object_name: str,
            file_path: str,
            content_type: Optional[str] = None,
            metadata: Optional[dict[str, str]] = None
    ) -> None:
        pass

    @abstractmethod
    async def upload_data(
            self,
            bucket_name: str,
            object_name: str,
            data: bytes,
            content_type: Optional[str] = None,
            metadata: Optional[dict[str, str]] = None
    ) -> None:
        pass

    @abstractmethod
    async def download_file(
            self,
            bucket_name: str,
            object_name: str,
            file_path: str
    ) -> None:
        pass

    @abstractmethod
    async def download_data(
            self,
            bucket_name: str,
            object_name: str
    ) -> bytes:
        pass

    @abstractmethod
    async def download_data_stream(
            self,
            bucket_name: str,
            object_name: str,
            chunk_size: int,
    ) -> AsyncIterator[bytes]:
        pass

    @abstractmethod
    async def delete_object(
            self,
            bucket_name: str,
            object_name: str
    ) -> None:
        pass

    @abstractmethod
    async def object_exists(
            self,
            bucket_name: str,
            object_name: str
    ) -> bool:
        pass

    @abstractmethod
    async def get_presigned_url(
            self,
            bucket_name: str,
            object_name: str,
            expires: Optional[int] = None,
            method: str = "GET"
    ) -> str:
        pass

    @abstractmethod
    async def list_objects(
            self,
            bucket_name: str,
            prefix: Optional[str] = None,
            recursive: bool = False
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def health_check(
            self,
            detailed: bool = False,
    ) -> dict[str, Any]:
        pass
