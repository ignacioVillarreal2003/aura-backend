from sqlalchemy import Column, Integer, String, Enum, DateTime
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

from app.domain.constants.document_status import DocumentStatus
from app.domain.constants.document_type import DocumentType


Base = declarative_base()

class Document(Base):
    __tablename__ = "document"

    id = Column(Integer, primary_key=True, index=True)

    file_name = Column(String(255), nullable=False)
    type = Column(Enum(DocumentType), nullable=False)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.pending)
    path = Column(String(255), nullable=True)

    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, nullable=True)
    deleted_at = Column(DateTime, nullable=True)