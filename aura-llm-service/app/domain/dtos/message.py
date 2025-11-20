from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str = Field(...)
    content: str = Field(...)