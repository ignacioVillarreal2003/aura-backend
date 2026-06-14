from dataclasses import dataclass
from typing import Literal

# External membership roles exposed to other services. We expose the granular
# owner/editor/reader role (instead of collapsing to owner vs member) so callers
# can distinguish read-only readers from writers — e.g. document deletion is
# allowed for any member that is not a reader.
ROLE_OWNER = "owner"
ROLE_EDITOR = "editor"
ROLE_READER = "reader"

ExternalMembershipRole = Literal["owner", "editor", "reader"]


@dataclass(frozen=True)
class ChatMembershipCheck:
    """Result of an internal chat-membership check for another microservice.

    ``role`` is ``None`` exactly when ``is_member`` is ``False``.
    """

    chat_id: int
    user_id: int
    is_member: bool
    role: ExternalMembershipRole | None
