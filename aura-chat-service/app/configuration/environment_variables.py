from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "Aura Chat Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "postgresql://aura_root:aura_password@db:5432/aura_db"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    
    # JWT Authentication
    JWT_SECRET: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60
    
    # LLM Service
    LLM_SERVICE_URL: str = "http://aura-llm-service:8000"
    LLM_DEFAULT_MODEL: str = "llama3"
    LLM_TIMEOUT_SECONDS: int = 120
    
    # Redis
    REDIS_URL: str = "redis://memory_db:6379/0"
    
    # Storage (MinIO)
    MINIO_ENDPOINT: str = "storage:9000"
    MINIO_ACCESS_KEY: str = "aura_root"
    MINIO_SECRET_KEY: str = "aura_password"
    MINIO_BUCKET: str = "chat-attachments"
    MINIO_SECURE: bool = False
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_MESSAGES_PER_MINUTE: int = 30
    RATE_LIMIT_CONVERSATIONS_PER_MINUTE: int = 10
    RATE_LIMIT_GLOBAL_PER_HOUR: int = 1000
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    MAX_MESSAGES_PAGE_SIZE: int = 200
    
    # CORS
    CORS_ORIGINS: str = "*"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

