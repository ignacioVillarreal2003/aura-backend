from pydantic import BaseModel

from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


class FragmentListResponse(BaseModel):
    fragments: list[FragmentResponse]

    model_config = {
        "from_attributes": True
    }
