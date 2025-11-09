from pydantic.v1 import BaseSettings


class EnvironmentVariables(BaseSettings):
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_driver: str = "postgresql+psycopg2"

    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool = False

    rabbitmq_host: str
    rabbitmq_port: int
    rabbitmq_user: str
    rabbitmq_password: str
    exchange: str
    queue: str

    environment: str = "development"

    class Config:
        env_file = ".env"

environment_variables = EnvironmentVariables()
