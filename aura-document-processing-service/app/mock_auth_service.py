from fastapi import FastAPI, Header, HTTPException, status
from typing import Optional

mock_auth_app = FastAPI(title="Mock Auth Service", version="1.0.0")

MOCK_USERS = {
    "user_token_123": {
        "id": 12,
        "email": "user@example.com",
        "username": "john_doe",
        "roles": ["user", "admin", "superuser"]
    },
    "admin_token_456": {
        "id": 22,
        "email": "admin@example.com",
        "username": "admin_user",
        "roles": ["user", "admin"]
    },
    "editor_token_789": {
        "id": 32,
        "email": "editor@example.com",
        "username": "editor_user",
        "roles": ["user", "editor"]
    },
    "superuser_token_000": {
        "id": 42,
        "email": "superuser@example.com",
        "username": "super_admin",
        "roles": ["user", "admin", "superuser"]
    }
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