from pydantic import BaseModel, Field


class Question(BaseModel):
    role: str = Field(...)
    content: str = Field(...)