from pgvector.sqlalchemy import VECTOR
from sqlalchemy import Column, Integer, String, DateTime, Text, BigInteger
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()

class FragmentORM(Base):
    __tablename__ = "fragments"

    id = Column(BigInteger, primary_key=True, index=True)
    source_document_id = Column(BigInteger, nullable=False)

    vector = Column(VECTOR(dim=1536), nullable=True)
    content = Column(Text, nullable=False)
    fragment_index = Column(Integer, nullable=False)

    embedding_model = Column(String(255), nullable=True)
    chunk_size = Column(Integer, nullable=False)

    created_by = Column(BigInteger, nullable=False)
    created_date = Column(DateTime, server_default=func.now())
    updated_by = Column(BigInteger, nullable=True)
    updated_date = Column(DateTime, nullable=True)
    deleted_by = Column(BigInteger, nullable=True)
    deleted_date = Column(DateTime, nullable=True)
