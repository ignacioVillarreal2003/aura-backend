from sqlalchemy import Column, Integer, String, Enum, DateTime
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from app.domain.constants.document_status import DocumentStatus
from app.domain.constants.document_type import DocumentType
from app.domain.constants.embedding_status import EmbeddingStatus


Base = declarative_base()

class DocumentORM(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    type = Column(Enum(DocumentType), nullable=False)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.pending)
    path = Column(String(255), nullable=True)

    size = Column(Integer, nullable=True)

    created_by = Column(Integer, nullable=False)
    created_date = Column(DateTime, server_default=func.now())
    updated_by = Column(Integer, nullable=True)
    updated_date = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, nullable=True)
    deleted_date = Column(DateTime, nullable=True)

    embedding_status = Column(Enum(EmbeddingStatus), default=EmbeddingStatus.pending)
    vector_count = Column(Integer, nullable=True)
    hash = Column(String(255), nullable=True)