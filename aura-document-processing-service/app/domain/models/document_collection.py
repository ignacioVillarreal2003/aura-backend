from sqlalchemy import Column, BigInteger, String, DateTime
from sqlalchemy.sql import func

from app.domain.models.base import Base


class DocumentCollection(Base):
    __tablename__ = "document_collection"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_by = Column(BigInteger, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(BigInteger, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
