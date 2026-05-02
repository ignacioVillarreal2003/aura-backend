from fastapi import FastAPI, Header, HTTPException, status
from typing import Optional

from prometheus_fastapi_instrumentator import Instrumentator
from pythonjsonlogger import jsonlogger
import logging
import sys

logger = logging.getLogger()
logHandler = logging.StreamHandler(sys.stdout)
formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(module)s %(message)s')
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

mock_auth_app = FastAPI(title="Mock Auth Service", version="1.0.0")
Instrumentator().instrument(mock_auth_app).expose(mock_auth_app)

MOCK_USERS = {
    "user_token_123": {
        "id": 12,
        "email": "user@example.com",
        "username": "john_doe",
        "roles": ["USER", "ADMIN", "SUPERADMIN"],
        "permissions": [
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

            "LIST_DOCUMENT_COLLECTIONS",
            "CREATE_DOCUMENT_COLLECTION",
            "GET_DOCUMENT_COLLECTION",
            "UPDATE_DOCUMENT_COLLECTION",
            "DELETE_DOCUMENT_COLLECTION",
            "LIST_DOCUMENT_COLLECTION_USERS",
            "ADD_DOCUMENT_COLLECTION_USER",
            "REMOVE_DOCUMENT_COLLECTION_USER",
            "LIST_DOCUMENT_COLLECTION_DOCUMENTS",
            "ADD_DOCUMENT_COLLECTION_DOCUMENT",
            "REMOVE_DOCUMENT_COLLECTION_DOCUMENT",
            "QUERY_KNOWLEDGE_GRAPH",
            "LLM_GRAPH_QUERY_TRANSLATION",
        ]
    },
}

def extract_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )

    return parts[1]


def get_user_from_token(token: str) -> dict:
    user = MOCK_USERS.get(token)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
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