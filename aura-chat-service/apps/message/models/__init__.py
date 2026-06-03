from apps.artifact.models.artifact_message import ArtifactMessage
from apps.message.models.message_bookmark import ArtifactBookmark, MessageBookmark
from apps.message.models.message_feedback import ArtifactFeedback, MessageFeedback
from apps.message.models.message_thread_reply import ArtifactThreadReply, MessageThreadReply
from apps.message.models.pinned_message import ArtifactPin, PinnedMessage

# ChatMessage is now ArtifactMessage — kept as alias for backward compatibility
ChatMessage = ArtifactMessage

__all__ = [
    "ArtifactMessage",
    "ChatMessage",
    "ArtifactBookmark",
    "MessageBookmark",
    "ArtifactFeedback",
    "MessageFeedback",
    "ArtifactThreadReply",
    "MessageThreadReply",
    "ArtifactPin",
    "PinnedMessage",
]
