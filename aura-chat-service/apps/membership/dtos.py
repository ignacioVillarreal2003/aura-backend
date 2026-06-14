from dataclasses import dataclass
from typing import Literal

# External membership roles exposed to other services. The internal
# owner/editor/reader model collapses to owner vs member, because callers only
# branch on ownership (e.g. bulk delete is owner-only).
ROLE_OWNER = "owner"
ROLE_MEMBER = "member"

ExternalMembershipRole = Literal["owner", "member"]


@dataclass(frozen=True)
class ChatMembershipCheck:
    """Result of an internal chat-membership check for another microservice.

    ``role`` is ``None`` exactly when ``is_member`` is ``False``.
    """

    chat_id: int
    user_id: int
    is_member: bool
    role: ExternalMembershipRole | None
