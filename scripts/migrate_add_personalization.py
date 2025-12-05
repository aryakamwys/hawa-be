#!/usr/bin/env python3
"""
Migration script untuk menambahkan field personalisasi dan language
Jalankan: poetry run python scripts/migrate_add_personalization.py
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from sqlalchemy import text
from app.db.postgres import engine

def run_migration():
    """Add personalization fields to users table"""
    with engine.connect() as conn:
        # Add new columns
        migrations = [
            # Language preference
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'id'",
            
            # Personalization fields
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS age INTEGER",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS occupation VARCHAR(100)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS location VARCHAR(100)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS activity_level VARCHAR(50)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS sensitivity_level VARCHAR(50)",
            
            # Encrypted health data
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS health_conditions_encrypted TEXT",
            
            # Privacy consent
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS privacy_consent BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS privacy_consent_date TIMESTAMP WITH TIME ZONE",
            
            # Updated timestamp
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()",
        ]
        
        for migration in migrations:
            try:
                conn.execute(text(migration))
                conn.commit()
                print(f"✓ {migration[:50]}...")
            except Exception as e:
                print(f"✗ Error: {e}")
                conn.rollback()
        
        print("\n✅ Migration completed!")

if __name__ == "__main__":
    run_migration()

