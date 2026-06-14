import concurrent.futures
import logging
import time
import httpx
from django.conf import settings

from core.authentication.authenticated_user import AuthenticatedUser
from core.authentication.authentication_provider import build_service_user_headers

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = [0, 2, 4]
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="docproc")


class DocumentProcessingClient:
    """Calls the document-processing service to clean up a chat's documents.

    Used as a side effect of deleting a chat: the chat service owns chats, the
    document-processing service owns the documents uploaded to them, so deleting
    a chat must ask that service to soft-delete the documents that belong to it.
    """

    def delete_documents_by_chat(self, chat_id: int, user: AuthenticatedUser) -> None:
        base = getattr(settings, "DOCUMENT_PROCESSING_SERVICE_URL", "").strip().rstrip("/")
        if not base:
            logger.warning(
                "Document processing service not configured "
                "(DOCUMENT_PROCESSING_SERVICE_URL missing), skipping document cleanup for chat %d.",
                chat_id,
            )
            return

        # Build the auth headers here, in the caller's request thread, so the
        # user's bearer token (held in a ContextVar) is forwarded downstream.
        # The worker thread that runs _dispatch would not see that ContextVar.
        headers = build_service_user_headers(user)
        headers["Accept"] = "application/json"

        timeout = getattr(settings, "DOCUMENT_PROCESSING_SERVICE_TIMEOUT", 5)
        _executor.submit(self._dispatch, chat_id, base, headers, timeout)

    def _dispatch(self, chat_id: int, base: str, headers: dict[str, str], timeout: int) -> None:
        url = f"{base}/api/v1/delete-document/soft/chat/{chat_id}"

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            if attempt > 1:
                time.sleep(_BACKOFF_SECONDS[attempt - 1])
            try:
                response = httpx.delete(url, headers=headers, timeout=timeout)
                if response.is_success:
                    logger.info(
                        "Requested document cleanup for chat %d (status %d).",
                        chat_id, response.status_code,
                    )
                    return
                logger.warning(
                    "Document service returned non-OK deleting documents for chat %d (attempt %d/%d).",
                    chat_id, attempt, _MAX_ATTEMPTS,
                    extra={"status": response.status_code, "body": response.text[:200]},
                )
                if response.status_code < 500:
                    return
            except httpx.RequestError as exc:
                if attempt == _MAX_ATTEMPTS:
                    logger.error(
                        "Failed to delete documents for chat %d after %d attempts: %s",
                        chat_id, _MAX_ATTEMPTS, exc,
                    )
                    return
                logger.debug(
                    "Document cleanup attempt %d for chat %d failed, retrying: %s",
                    attempt, chat_id, exc,
                )

        logger.error(
            "Failed to delete documents for chat %d after %d attempts (HTTP errors).",
            chat_id, _MAX_ATTEMPTS,
        )


document_processing_client = DocumentProcessingClient()
