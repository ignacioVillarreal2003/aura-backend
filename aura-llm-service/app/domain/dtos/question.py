from pydantic import BaseModel


class Question(BaseModel):
    role: str
    content: str