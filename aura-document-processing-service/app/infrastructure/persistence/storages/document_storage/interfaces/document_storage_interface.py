from abc import ABC, abstractmethod
from typing import BinaryIO
from fastapi import UploadFile


class DocumentStorageInterface(ABC):
    @abstractmethod
    def upload_document(
            self,
            document: UploadFile
    ) -> str:
        pass

    @abstractmethod
    def download_document(
            self,
            document_path: str
    ) -> BinaryIO:
        pass

    @abstractmethod
    def delete_document(
            self,
            document_path: str
    ) -> None:
        pass
