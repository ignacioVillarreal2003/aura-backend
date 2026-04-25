from sqlalchemy import Column, BigInteger, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.infrastructure.persistence.database.orm.base import Base


class UserInDocumentCollection(Base):
    __tablename__ = "user_in_document_collection"

    id = Column(BigInteger, primary_key=True, index=True)
    document_collection_id = Column(
        BigInteger,
        ForeignKey("document_collection.id"),
        nullable=False
    )
    user_id = Column(BigInteger, nullable=False)
    
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_by = Column(BigInteger, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
