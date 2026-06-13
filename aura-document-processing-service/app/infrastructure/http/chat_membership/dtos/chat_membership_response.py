from typing import Optional
from pydantic import BaseModel

CHAT_ROLE_OWNER = "owner"
CHAT_ROLE_MEMBER = "member"


class ChatMembershipResponse(BaseModel):
    """Result of asking the chat microservice whether a user belongs to a chat.

    ``role`` is the user's role within the chat (e.g. ``owner``/``member``) and
    is ``None`` when the user is not a member.
    """

    is_member: bool
    role: Optional[str] = None

    model_config = {"frozen": True}

    @property
    def is_owner(self) -> bool:
        return self.is_member and self.role == CHAT_ROLE_OWNER
