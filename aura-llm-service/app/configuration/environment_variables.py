from pydantic.v1 import BaseSettings


class EnvironmentVariables(BaseSettings):
    ollama_base_url: str
    ollama_model_name: str

    fragment_retrieve_url: str

    rabbitmq_host: str
    rabbitmq_port: int
    rabbitmq_user: str
    rabbitmq_password: str
    exchange: str
    question_queue: str
    answer_queue: str

    class Config:
        env_file = ".env"


environment_variables = EnvironmentVariables()
