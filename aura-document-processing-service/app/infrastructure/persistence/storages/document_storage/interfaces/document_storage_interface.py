from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from fastapi import UploadFile


class DocumentStorageInterface(ABC):
    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def upload_document(
            self,
            file: UploadFile,
            document_id: Optional[str] = None,
            additional_metadata: Optional[Dict[str, str]] = None
    ) -> str:
        pass

    @abstractmethod
    async def download_document(
            self,
            object_name: str
    ) -> bytes:
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
            method: str,
            expires: Optional[int] = None
    ) -> str:
        pass

    @abstractmethod
    async def list_documents(
            self,
            recursive: bool = True,
            prefix: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_metrics(self) -> Dict[str, int]:
        pass
