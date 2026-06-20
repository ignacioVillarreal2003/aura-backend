from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Optional
from fastapi import UploadFile


class DocumentStorageInterface(ABC):
    @abstractmethod
    async def start(
            self
    ) -> None:
        pass

    @abstractmethod
    async def upload_document(
            self,
            file: UploadFile,
            document_id: Optional[str] = None,
            additional_metadata: Optional[dict[str, str]] = None
    ) -> str:
        pass

    @abstractmethod
    async def upload_document_from_path(
            self,
            file_path: str,
            original_filename: str,
            document_id: Optional[str] = None,
            additional_metadata: Optional[dict[str, str]] = None,
            content_type: Optional[str] = None,
    ) -> str:
        pass

    @abstractmethod
    async def download_document(
            self,
            object_name: str
    ) -> bytes:
        pass

    @abstractmethod
    def download_document_stream(
            self,
            object_name: str,
            chunk_size: int,
    ) -> AsyncIterator[bytes]:
        pass

    @abstractmethod
    async def download_document_to_file(
            self,
            object_name: str,
            file_path: str
    ) -> None:
        pass

    @abstractmethod
    async def delete_document(
            self,
            object_name: str
    ) -> None:
        pass

    @abstractmethod
    async def document_exists(
            self,
            object_name: str
    ) -> bool:
        pass

    @abstractmethod
    async def get_presigned_url(
            self,
            object_name: str,
            method: str = "GET",
            expires: Optional[int] = None
    ) -> str:
        pass

    @abstractmethod
    async def list_documents(
            self,
            recursive: bool = True,
            prefix: Optional[str] = None
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def health_check(
            self,
            detailed: bool = False,
    ) -> dict[str, Any]:
        pass
