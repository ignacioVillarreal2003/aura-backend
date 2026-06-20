from typing import Optional
from pydantic import BaseModel

CHAT_ROLE_OWNER = "owner"
CHAT_ROLE_EDITOR = "editor"
CHAT_ROLE_READER = "reader"


class ChatMembershipResponse(BaseModel):
    is_member: bool
    role: Optional[str] = None

    model_config = {"frozen": True}

    @property
    def is_owner(self) -> bool:
        return self.is_member and self.role == CHAT_ROLE_OWNER

    @property
    def can_modify(self) -> bool:
        return self.is_member and self.role != CHAT_ROLE_READER
