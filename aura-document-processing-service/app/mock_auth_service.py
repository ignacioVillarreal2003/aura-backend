from fastapi import FastAPI, Header, HTTPException, status
from typing import Optional

mock_auth_app = FastAPI(title="Mock Auth Service", version="1.0.0")

MOCK_USERS = {
    "user_token_123": {
        "id": 12,
        "email": "user@example.com",
        "username": "john_doe",
        "roles": ["user"]
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


@mock_auth_app.post("/auth/verify-permissions")
async def verify_permissions(
        roles_required: dict,
        authorization: str = Header(None)
):
    token = extract_token(authorization)
    user = get_user_from_token(token)

    required_roles = roles_required.get("roles", [])
    user_roles = user.get("roles", [])

    # Verificar si tiene al menos uno de los roles requeridos
    has_permission = any(role in user_roles for role in required_roles)

    if not has_permission:
        print(f"❌ Permission denied for {user['email']} - Required: {required_roles}, Has: {user_roles}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Required roles: {', '.join(required_roles)}"
        )

    print(f"✅ Permission granted for {user['email']} - Required: {required_roles}, Has: {user_roles}")

    return user


@mock_auth_app.get("/auth/user")
async def get_user_by_token(authorization: str = Header(None)):
    token = extract_token(authorization)
    user = get_user_from_token(token)

    print(f"✅ User retrieved: {user['email']}")

    return user

@mock_auth_app.post("/auth/simulate-error")
async def simulate_error(error_type: str):
    if error_type == "unauthorized":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Simulated unauthorized error"
        )
    elif error_type == "forbidden":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Simulated forbidden error"
        )
    elif error_type == "not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulated not found error"
        )
    elif error_type == "timeout":
        import asyncio
        await asyncio.sleep(30)  # Simular timeout

    return {"message": "No error"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mock_auth_app, host="0.0.0.0", port=8080)