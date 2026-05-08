from __future__ import annotations

import logging
import sys
from typing import Iterable, Optional

from fastapi import FastAPI, Header, HTTPException, status
from prometheus_fastapi_instrumentator import Instrumentator
from pythonjsonlogger import jsonlogger

logger = logging.getLogger()
logHandler = logging.StreamHandler(sys.stdout)
formatter = jsonlogger.JsonFormatter(
    "%(asctime)s %(levelname)s %(name)s %(module)s %(message)s"
)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

mock_auth_app = FastAPI(title="Mock Auth Service", version="1.0.0")
Instrumentator().instrument(mock_auth_app).expose(mock_auth_app)


def _merge_permission_groups(*groups: Iterable[str]) -> list[str]:
    """Stable de-duplication across microservice buckets."""
    seen: set[str] = set()
    out: list[str] = []
    for group in groups:
        for perm in group:
            if perm not in seen:
                seen.add(perm)
                out.append(perm)
    return out


DOCUMENT_PROCESSING_SERVICE_PERMISSIONS: list[str] = [
    "INGEST_DOCUMENT",
    "GET_DOCUMENT",
    "LIST_DOCUMENTS",
    "LIST_DOCUMENTS_BY_CHAT",
    "DOWNLOAD_DOCUMENT",
    "SOFT_DELETE_DOCUMENT",
    "SOFT_DELETE_DOCUMENTS_BY_CHAT",
    "POST_PROCESS_DOCUMENTS_START_ALL",
    "POST_PROCESS_DOCUMENTS_START",
    "POST_PROCESS_DOCUMENTS_STATUS",
    "POST_PROCESS_DOCUMENTS_STOP",
    "POST_PROCESS_FRAGMENTS_START_ALL",
    "POST_PROCESS_FRAGMENTS_START",
    "POST_PROCESS_FRAGMENTS_STATUS",
    "POST_PROCESS_FRAGMENTS_STOP",
    "LIST_CONTEXT_FRAGMENTS_BY_QUESTION",
    "LIST_CONTEXT_FRAGMENTS_BY_DOCUMENTS",
    "GRAPH_QUERY",
    "GRAPH_ENTITY",
    "GRAPH_PATH",
]

DOCUMENT_COLLECTION_SERVICE_PERMISSIONS: list[str] = [
    "LIST_DOCUMENT_COLLECTIONS",
    "CREATE_DOCUMENT_COLLECTION",
    "GET_DOCUMENT_COLLECTION",
    "UPDATE_DOCUMENT_COLLECTION",
    "DELETE_DOCUMENT_COLLECTION",
    "LIST_DOCUMENT_COLLECTION_DOCUMENTS",
    "ADD_DOCUMENT_COLLECTION_DOCUMENT",
    "REMOVE_DOCUMENT_COLLECTION_DOCUMENT",
    "LIST_CLASSIFICATION_LEVELS",
    "CREATE_CLASSIFICATION_LEVEL",
    "GET_CLASSIFICATION_LEVEL",
    "UPDATE_CLASSIFICATION_LEVEL",
    "DELETE_CLASSIFICATION_LEVEL",
    "LIST_COMPARTMENTS",
    "CREATE_COMPARTMENT",
    "GET_COMPARTMENT",
    "UPDATE_COMPARTMENT",
    "DELETE_COMPARTMENT",
    "GET_USER_AUTHORIZATION",
    "SET_USER_CLEARANCE",
    "DELETE_USER_CLEARANCE",
    "LIST_USER_COMPARTMENTS",
    "ADD_USER_COMPARTMENT",
    "REMOVE_USER_COMPARTMENT",
    "GET_USER_ACCESSIBLE_COLLECTIONS",
]

LLM_SERVICE_PERMISSIONS: list[str] = [
    "LLM_DOCUMENT_QUESTION",
    "LLM_DOCUMENT_QUESTION_STREAM",
    "LLM_DOCUMENT_SUMMARY",
    "LLM_DOCUMENT_ACTION",
    "LLM_AGENT",
    "LLM_DOCUMENT_CLASSIFY",
    "LLM_FRAGMENT_ENRICH",
    "LLM_GRAPH_EXTRACTION",
    "LLM_GRAPH_QUERY_TRANSLATION",
]

CHAT_SERVICE_PERMISSIONS: list[str] = [
    "LIST_CHATS",
    "LIST_MY_CHATS",
    "LIST_ARCHIVED_CHATS",
    "CREATE_CHAT",
    "GET_CHAT",
    "UPDATE_CHAT",
    "DELETE_CHAT",
    "PIN_CHAT",
    "ARCHIVE_CHAT",
    "UNARCHIVE_CHAT",
    "LOCK_CHAT",
    "MUTE_CHAT",
    "LIST_SHARE_LINKS",
    "CREATE_SHARE_LINK",
    "DELETE_SHARE_LINK",
    "LIST_WEBHOOKS",
    "CREATE_WEBHOOK",
    "UPDATE_WEBHOOK",
    "DELETE_WEBHOOK",
    "LIST_MEMBERS",
    "ADD_MEMBER",
    "UPDATE_MEMBER",
    "REMOVE_MEMBER",
    "LEAVE_CHAT",
    "UPDATE_MEMBER_ROLE",
    "LIST_MESSAGES",
    "SEND_MESSAGE",
    "DELETE_MESSAGE",
    "CLEAR_CHAT_HISTORY",
    "MARK_CHAT_AS_READ",
    "REGENERATE_AI_RESPONSE",
    "LIST_BOOKMARKS",
    "BOOKMARK_MESSAGE",
    "LIST_PINNED_MESSAGES",
    "PIN_MESSAGE",
    "SET_MESSAGE_FEEDBACK",
    "LIST_THREAD_REPLIES",
    "ADD_THREAD_REPLY",
    "EXPORT_CHAT",
]

MOCK_USERS = {
    "user_token_123": {
        "id": 12,
        "email": "user@example.com",
        "username": "john_doe",
        "roles": ["USER", "ADMIN", "SUPERADMIN"],
        "permissions": _merge_permission_groups(
            DOCUMENT_PROCESSING_SERVICE_PERMISSIONS,
            DOCUMENT_COLLECTION_SERVICE_PERMISSIONS,
            LLM_SERVICE_PERMISSIONS,
            CHAT_SERVICE_PERMISSIONS,
        ),
    },
}


def extract_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )

    return parts[1]


def get_user_from_token(token: str) -> dict:
    user = MOCK_USERS.get(token)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    return user


@mock_auth_app.get("/auth/validate")
async def validate_token(authorization: str = Header(None)):
    token = extract_token(authorization)
    user = get_user_from_token(token)

    print(f"✅ Token validated: {token[:20]}... -> User: {user['email']}")

    return user


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(mock_auth_app, host="0.0.0.0", port=8080)
