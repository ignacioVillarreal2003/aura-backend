from typing import Protocol, BinaryIO
from fastapi import UploadFile


class DocumentStorageServiceInterface(Protocol):
    async def upload_document(self,
                              file: UploadFile) -> str:
        ...

    async def download_document(self, file_key: str) -> BinaryIO:
        ...

    async def delete_document(self,
                              file_key: str) -> None:
        ...

    async def document_exists(self, file_key: str) -> bool:
        ...