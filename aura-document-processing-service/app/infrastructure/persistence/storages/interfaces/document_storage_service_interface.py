from typing import Protocol, BinaryIO
from fastapi import UploadFile


class DocumentStorageServiceInterface(Protocol):
    def upload_document(self,
                              file: UploadFile) -> str:
        ...

    def download_document(self, file_key: str) -> BinaryIO:
        ...

    def delete_document(self,
                              file_key: str) -> None:
        ...

    def document_exists(self, file_key: str) -> bool:
        ...