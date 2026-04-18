from pydantic import BaseModel, Field

MAX_ID = 2_147_483_647
MAX_ERROR_MESSAGE_CHARS = 500


class PostProcessDocumentError(BaseModel):
    document_id: int = Field(..., gt=0, le=MAX_ID)
    error: str = Field(..., min_length=1, max_length=MAX_ERROR_MESSAGE_CHARS)
