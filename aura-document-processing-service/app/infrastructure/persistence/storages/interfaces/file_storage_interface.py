from typing import Protocol, BinaryIO

from fastapi import UploadFile


class FileStorageInterface(Protocol):
    def upload(self,
               file: UploadFile) -> str:
        ...

    def download(self,
                 file_key: str) -> BinaryIO:
        ...

    def delete(self,
               file_key: str):
        ...
