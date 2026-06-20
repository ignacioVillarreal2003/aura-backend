from abc import ABC, abstractmethod


class DocumentCollectionCatalogClientInterface(ABC):
    @abstractmethod
    async def fetch_all_accessible_document_ids(
            self,
            *,
            user_id: int,
            authorization_header: str | None,
    ) -> frozenset[int]:
        pass
