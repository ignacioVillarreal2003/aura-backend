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
    minio_secure: bool = False

    cleaner_type: str = "basic"
    splitter_type: str = "recursive"
    embedder_type: str = "huggingface"
    vector_dimension: int = 384
    split_size: int = 600,
    split_overlap: int = 60

    rabbitmq_host: str
    rabbitmq_port: int
    rabbitmq_user: str
    rabbitmq_password: str
    exchange: str
    question_queue: str

    max_file_size_mb: int = 20
    environment: str = "development"

    class Config:
        env_file = ".env"

environment_variables = EnvironmentVariables()
