import logging
from typing import Any, Optional
import httpx

from app.infrastructure.http.document_collection_catalog.interfaces.document_collection_catalog_client_interface import (
    DocumentCollectionCatalogClientInterface,
)
from app.infrastructure.http.document_collection_catalog.document_collection_catalog_settings import (
    DocumentCollectionCatalogSettings,
)
from app.infrastructure.http.http_client.exceptions.http_client_exceptions import HttpClientException
from app.infrastructure.http.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)


class DocumentCollectionCatalogClient(DocumentCollectionCatalogClientInterface):
    def __init__(
            self,
            http_client: HttpClientInterface,
            settings: Optional[DocumentCollectionCatalogSettings] = None,
    ) -> None:
        self._http_client = http_client
        self._settings = settings or DocumentCollectionCatalogSettings()

    async def fetch_all_accessible_document_ids(
            self,
            *,
            user_id: int,
            authorization_header: str | None,
    ) -> frozenset[int]:
        headers = self._build_request_headers(authorization_header=authorization_header)
        if headers is None:
            logger.debug(
                "Skipping accessible-documents fetch: no credentials available.",
                extra={"user_id": user_id},
            )
            return frozenset()

        url = f"{self._settings.accessible_collections_url.rstrip('/')}/{user_id}/accessible-documents/"
        ids: set[int] = set()
        pages_read = 0
        timeout = self._settings.request_timeout_seconds

        try:
            while url and pages_read < self._settings.max_pages:
                if pages_read == 0:
                    response = await self._http_client.get(
                        url,
                        headers=headers,
                        params={"page_size": self._settings.page_size},
                        timeout=timeout,
                    )
                else:
                    response = await self._http_client.get(
                        url,
                        headers=headers,
                        timeout=timeout,
                    )
                pages_read += 1
                if response.status_code >= 400:
                    logger.warning(
                        "Accessible documents request failed.",
                        extra={
                            "user_id": user_id,
                            "status_code": response.status_code,
                        },
                    )
                    return frozenset()

                payload_any: Any = response.json()
                if not isinstance(payload_any, dict):
                    logger.warning(
                        "Unexpected accessible-documents payload shape.",
                        extra={"user_id": user_id},
                    )
                    return frozenset()

                payload = payload_any
                results = payload.get("results")
                if isinstance(results, list):
                    for row in results:
                        if isinstance(row, dict):
                            doc_id = row.get("document_id")
                            if isinstance(doc_id, int):
                                ids.add(doc_id)
                            elif isinstance(doc_id, str) and doc_id.isdigit():
                                ids.add(int(doc_id))

                nxt = payload.get("next")
                if isinstance(nxt, str) and nxt.strip():
                    url = nxt.strip()
                else:
                    url = ""

            if pages_read >= self._settings.max_pages:
                logger.warning(
                    "Stopped paginating accessible-documents after max_pages.",
                    extra={"user_id": user_id, "max_pages": self._settings.max_pages},
                )

        except (HttpClientException, httpx.RequestError):
            logger.exception(
                "Error while fetching accessible documents.",
                extra={"user_id": user_id},
            )
            return frozenset()
        except ValueError:
            logger.exception(
                "Invalid JSON while fetching accessible documents.",
                extra={"user_id": user_id},
            )
            return frozenset()

        return frozenset(ids)

    def _build_request_headers(
            self,
            *,
            authorization_header: str | None,
    ) -> dict[str, str] | None:
        bearer = self._normalize_bearer(authorization_header)
        if bearer is None:
            return None
        return {
            "Authorization": bearer,
            "Accept": "application/json",
        }

    @staticmethod
    def _normalize_bearer(raw: Optional[str]) -> Optional[str]:
        if raw is None:
            return None
        stripped = raw.strip()
        if not stripped:
            return None
        if stripped.lower().startswith("bearer "):
            return stripped
        return f"Bearer {stripped}"
