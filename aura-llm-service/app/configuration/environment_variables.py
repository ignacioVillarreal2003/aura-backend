from pydantic.v1 import BaseSettings


class EnvironmentVariables(BaseSettings):
    ollama_url: str
    model_name: str

    rabbitmq_host: str
    rabbitmq_port: int
    rabbitmq_user: str
    rabbitmq_password: str
    exchange: str
    question_queue: str

    class Config:
        env_file = ".env"


environment_variables = EnvironmentVariables()
