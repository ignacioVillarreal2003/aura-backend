from pydantic.v1 import BaseSettings


class EnvironmentVariables(BaseSettings):
    ollama_url: str
    model_name: str

    class Config:
        env_file = ".env"


environment_variables = EnvironmentVariables()
