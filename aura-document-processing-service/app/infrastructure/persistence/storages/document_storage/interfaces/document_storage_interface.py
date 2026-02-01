from abc import ABC, abstractmethod
from typing import BinaryIO

from fastapi import UploadFile


class DocumentStorageInterface(ABC):
    @abstractmethod
    def upload(
            self,
            document: UploadFile
    ) -> str:
        pass

    @abstractmethod
    def download(
            self,
            document_key: str
    ) -> BinaryIO:
        pass

    @abstractmethod
    def delete(
            self,
            document_key: str
    ) -> None:
        pass
