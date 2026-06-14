from typing import Optional
from pydantic import BaseModel

CHAT_ROLE_OWNER = "owner"
CHAT_ROLE_EDITOR = "editor"
CHAT_ROLE_READER = "reader"
# Legacy collapsed role; kept so older responses still resolve sensibly.
CHAT_ROLE_MEMBER = "member"


class ChatMembershipResponse(BaseModel):
    """Result of asking the chat microservice whether a user belongs to a chat.

    ``role`` is the user's role within the chat (``owner``/``editor``/``reader``)
    and is ``None`` when the user is not a member.
    """

    is_member: bool
    role: Optional[str] = None

    model_config = {"frozen": True}

    @property
    def is_owner(self) -> bool:
        return self.is_member and self.role == CHAT_ROLE_OWNER

    @property
    def can_modify(self) -> bool:
        """Whether the user may modify/delete content in the chat.

        Owners and editors can; readers are read-only. Members with an unknown
        (legacy) role are allowed, since only readers are explicitly restricted.
        """
        return self.is_member and self.role != CHAT_ROLE_READER
