from datetime import datetime
from typing import TYPE_CHECKING, Optional
import enum

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.domain.models.base import Base

if TYPE_CHECKING:
    from app.domain.models.conversation import Chat


class MembershipStatus(enum.Enum):
    active = "active"
    inactive = "inactive"
    pending = "pending"


class ChatMembership(Base):
    __tablename__ = "chat_membership"
    __table_args__ = (
        UniqueConstraint("member_id", "chat_id", name="chat_membership_member_chat_unique"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    member_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chat.id"), nullable=False)
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(MembershipStatus, name="chat_membership_status"),
        nullable=False
    )
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    chat: Mapped["Chat"] = relationship("Chat", back_populates="memberships")

    def __repr__(self) -> str:
        return f"<ChatMembership(id={self.id}, member_id={self.member_id}, chat_id={self.chat_id})>"

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
