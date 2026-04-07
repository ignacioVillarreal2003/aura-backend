from pydantic import BaseModel

from app.domain.dtos.fragment.fragment_query.fragment_response import FragmentResponse


class FragmentListResponse(BaseModel):
    fragments: list[FragmentResponse]

    model_config = {
        "from_attributes": True
    }
