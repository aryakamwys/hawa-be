"""
Vector Database Service untuk Weather Knowledge
Menggunakan pgvector untuk similarity search
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any, Optional
import os

from app.db.models.weather_knowledge import WeatherKnowledge


class VectorService:
    """Service untuk manage vector embeddings dan similarity search"""
    
    def __init__(self):
        # Gunakan sentence-transformers untuk embeddings lokal
        try:
            from sentence_transformers import SentenceTransformer
            # Model multilingual untuk support 3 bahasa
            self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            self.embedding_dim = 384
        except ImportError:
            self.embedding_model = None
            self.embedding_dim = 384
            print("Warning: sentence-transformers not available, embeddings will be disabled")

        # Toggle pgvector usage via env (default: False untuk hindari error casting)
        self.use_pgvector = os.getenv("USE_PGVECTOR", "false").lower() == "true"
    
    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding untuk text"""
        if not self.embedding_model:
            raise ValueError("Embedding model not initialized. Install sentence-transformers.")
        
        embedding = self.embedding_model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def search_similar(
        self,
        db: Session,
        query: str,
        language: str = "id",
        limit: int = 3,
        threshold: float = 0.7
    ) -> List[str]:
        """
        Search similar knowledge menggunakan vector similarity
        
        Args:
            db: Database session
            query: Query text untuk search
            language: Language filter (id, en, su)
            limit: Maximum results
            threshold: Minimum similarity score
        
        Returns:
            List of content strings
        """
        if not self.embedding_model or not self.use_pgvector:
            # Fallback jika embeddings tidak ada atau pgvector dimatikan
            return self._fallback_text_search(db, query, language, limit)
        
        try:
            query_embedding = self.get_embedding(query)
            
            # Convert to PostgreSQL array format
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
            
            # PostgreSQL vector similarity search
            # Menggunakan cosine distance (<=> operator)
            sql_query = text("""
                SELECT content, knowledge_metadata,
                       1 - (embedding <=> :embedding::vector) as similarity
                FROM weather_knowledge
                WHERE language = :language
                  AND embedding IS NOT NULL
                  AND 1 - (embedding <=> :embedding::vector) > :threshold
                ORDER BY embedding <=> :embedding::vector
                LIMIT :limit
            """)
            
            result = db.execute(
                sql_query,
                {
                    "embedding": embedding_str,
                    "language": language,
                    "threshold": threshold,
                    "limit": limit
                }
            )
            
            rows = result.fetchall()
            return [row.content for row in rows]
            
        except Exception as e:
            # Fallback jika pgvector error
            print(f"Warning: Vector search failed: {e}. Falling back to text search.")
            return self._fallback_text_search(db, query, language, limit)
    
    def _fallback_text_search(
        self,
        db: Session,
        query: str,
        language: str,
        limit: int
    ) -> List[str]:
        """Fallback text search jika vector search tidak available"""
        try:
            results = db.query(WeatherKnowledge).filter(
                WeatherKnowledge.language == language
            ).limit(limit).all()
            
            return [r.content for r in results]
        except Exception:
            return []
    
    def add_knowledge(
        self,
        db: Session,
        content: str,
        metadata: Dict[str, Any],
        language: str = "id"
    ) -> WeatherKnowledge:
        """
        Add knowledge ke vector database
        
        Args:
            db: Database session
            content: Knowledge content
            metadata: Metadata (source, category, etc.)
            language: Language (id, en, su)
        
        Returns:
            Created WeatherKnowledge object
        """
        if not self.embedding_model or not self.use_pgvector:
            # Jika pgvector dimatikan atau model tidak ada, simpan tanpa embedding
            knowledge = WeatherKnowledge(
                content=content,
                embedding=None,
                knowledge_metadata=metadata,
                language=language
            )
        else:
            embedding = self.get_embedding(content)
            embedding_str = "[" + ",".join(map(str, embedding)) + "]"
            
            knowledge = WeatherKnowledge(
                content=content,
                embedding=embedding_str,  # Will be converted by pgvector
                knowledge_metadata=metadata,
                language=language
            )
        
        db.add(knowledge)
        db.commit()
        db.refresh(knowledge)
        
        return knowledge

