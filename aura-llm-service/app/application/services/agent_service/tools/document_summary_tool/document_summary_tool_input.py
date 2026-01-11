from pydantic import BaseModel


class DocumentSummaryToolInput(BaseModel):
    document_id: int