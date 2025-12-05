"""
Weather Knowledge Model untuk Vector Database
Menyimpan knowledge base tentang polusi udara dan kesehatan
"""
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.db.postgres import Base

# Import Vector type untuk pgvector
try:
    from pgvector.sqlalchemy import Vector
    VECTOR_AVAILABLE = True
except ImportError:
    # Fallback jika pgvector belum terinstall
    VECTOR_AVAILABLE = False
    # Dummy Vector type untuk development
    from sqlalchemy import TypeDecorator, String as SQLString
    class Vector(TypeDecorator):
        impl = SQLString
        cache_ok = True


class WeatherKnowledge(Base):
    """Knowledge base untuk rekomendasi cuaca dengan vector embeddings"""
    __tablename__ = "weather_knowledge"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Knowledge content
    
    # Vector embedding (1536 dimensions untuk OpenAI, atau 384 untuk sentence-transformers)
    embedding: Mapped[Vector] = mapped_column(
        Vector(384) if VECTOR_AVAILABLE else None,  # sentence-transformers default
        nullable=True
    )
    
    # Metadata untuk tracking (rename dari 'metadata' karena reserved di SQLAlchemy)
    knowledge_metadata: Mapped[dict] = mapped_column(JSON, nullable=True)  # Source, date, category, etc.
    
    # Language support
    language: Mapped[str] = mapped_column(String(10), default="id")  # id, en, su
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )

