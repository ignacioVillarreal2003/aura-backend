from datetime import datetime
from typing import TYPE_CHECKING, Optional
import enum
import uuid

from sqlalchemy import String, Text, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.domain.models.base import Base

if TYPE_CHECKING:
    from app.domain.models.conversation import Conversation
    from app.domain.models.attachment import Attachment
    from app.domain.models.tool_call import ToolCall


class MessageRole(enum.Enum):
    """Role of the message sender (OpenAI-compatible)."""
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class MessageStatus(enum.Enum):
    """Status of a message."""
    draft = "draft"
    streaming = "streaming"
    complete = "complete"
    error = "error"


class Message(Base):
    """
    Represents a single message within a conversation.
    
    Messages can be from the system, user, assistant, or tool.
    """
    __tablename__ = "message"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Foreign key
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation.id", ondelete="CASCADE"),
        nullable=False
    )

    # Message content
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole),
        nullable=False
    )
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus),
        default=MessageStatus.complete,
        nullable=False
    )

    # Token tracking
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # For assistant responses
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    finish_reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Extensible metadata
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # For tool messages
    tool_call_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Order within conversation
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment",
        back_populates="message",
        lazy="selectin"
    )
    tool_calls: Mapped[list["ToolCall"]] = relationship(
        "ToolCall",
        back_populates="message",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role.value}, seq={self.sequence_number})>"

    @property
    def is_deleted(self) -> bool:
        """Check if the message is soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark the message as deleted."""
        self.deleted_at = datetime.utcnow()

