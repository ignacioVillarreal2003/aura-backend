from fastapi import FastAPI, Header, HTTPException, status
from typing import Optional
from prometheus_fastapi_instrumentator import Instrumentator
import logging
from pythonjsonlogger import jsonlogger

mock_auth_app = FastAPI(title="Mock Auth Service", version="1.0.0")

# Set up JSON logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    '%(asctime)s %(levelname)s %(name)s %(message)s'
)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

Instrumentator().instrument(mock_auth_app).expose(mock_auth_app)

MOCK_USERS = {
    "user_token_123": {
        "id": 12,
        "email": "user@example.com",
        "username": "john_doe",
        "roles": ["user", "admin", "superadmin"],
        "permissions": [
            "DOCUMENT_CREATE",
            "DOCUMENT_UPDATE",
            "DOCUMENT_DELETE",
            "DOCUMENT_GET",
            "FRAGMENT_CREATE",
            "FRAGMENT_UPDATE",
            "FRAGMENT_DELETE",
            "FRAGMENT_GET"
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

    logger.info("Token validated successfully", extra={
        "audit_event": True,
        "valid_token": True,
        "email": user['email']
    })

    return user

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mock_auth_app, host="0.0.0.0", port=8080)