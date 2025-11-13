from pydantic import BaseModel

class FragmentResponse(BaseModel):
    id: int
    document_id: int
    content: str

    model_config = {
        "from_attributes": True  # <-- Pydantic V2
    }