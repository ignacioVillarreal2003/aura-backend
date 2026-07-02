from dataclasses import dataclass
from typing import Literal

ROLE_OWNER = "owner"
ROLE_EDITOR = "editor"
ROLE_READER = "reader"

ExternalMembershipRole = Literal["owner", "editor", "reader"]


@dataclass(frozen=True)
class ChatMembershipCheck:

    chat_id: int
    user_id: int
    is_member: bool
    role: ExternalMembershipRole | None
