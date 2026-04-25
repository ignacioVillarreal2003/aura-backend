from sqlalchemy import Column, BigInteger, String, DateTime, Text
from sqlalchemy.sql import func

from app.infrastructure.persistence.database.orm.base import Base


class Chat(Base):
    __tablename__ = "chat"

    id = Column(BigInteger, primary_key=True, index=True)

    name = Column(String(255), nullable=False)

    system_prompt = Column(Text, nullable=True)
    response_style = Column(Text, nullable=True)

    last_message_at = Column(DateTime(timezone=True), nullable=True)

    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_by = Column(BigInteger, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(BigInteger, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
