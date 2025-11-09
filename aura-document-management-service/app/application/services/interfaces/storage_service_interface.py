from typing import Protocol
from fastapi import UploadFile


class StorageServiceInterface(Protocol):
    async def upload_document(self,
                              file: UploadFile) -> str:
        ...