from typing import Protocol


class DocumentPublisherInterface(Protocol):
    def publish_document(self,
                         document_id: int) -> None:
        ...