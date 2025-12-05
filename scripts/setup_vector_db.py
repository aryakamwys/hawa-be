#!/usr/bin/env python3
"""
Setup script untuk vector database (weather_knowledge table)
Jalankan: python3 scripts/setup_vector_db.py
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from sqlalchemy import text
from app.db.postgres import engine

def setup_vector_db():
    """Setup weather_knowledge table dengan vector support"""
    with engine.connect() as conn:
        # Check if pgvector extension is available
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            print("✓ pgvector extension created/enabled")
        except Exception as e:
            print(f"⚠ Warning: Could not enable pgvector extension: {e}")
            print("  Continuing without vector support (fallback mode)")
        
        # Create weather_knowledge table
        try:
            # Drop table if exists (for development)
            conn.execute(text("DROP TABLE IF EXISTS weather_knowledge"))
            conn.commit()
            
            # Create table with vector support
            create_table_sql = """
            CREATE TABLE weather_knowledge (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                embedding vector(384),
                knowledge_metadata JSONB,
                language VARCHAR(10) DEFAULT 'id',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            """
            conn.execute(text(create_table_sql))
            conn.commit()
            print("✓ weather_knowledge table created")
            
            # Create index for vector similarity search
            try:
                conn.execute(text("""
                    CREATE INDEX ON weather_knowledge 
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                """))
                conn.commit()
                print("✓ Vector index created")
            except Exception as e:
                print(f"⚠ Warning: Could not create vector index: {e}")
                print("  Table created but without vector index")
            
            # Create index for language
            conn.execute(text("CREATE INDEX idx_weather_knowledge_language ON weather_knowledge(language)"))
            conn.commit()
            print("✓ Language index created")
            
        except Exception as e:
            print(f"✗ Error creating table: {e}")
            conn.rollback()
            return False
        
        print("\n✅ Vector database setup completed!")
        return True

if __name__ == "__main__":
    setup_vector_db()

