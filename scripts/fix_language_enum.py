#!/usr/bin/env python3
"""
Fix language enum values di database
Update dari lowercase ('id', 'en', 'su') ke uppercase ('ID', 'EN', 'SU')
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from sqlalchemy import text
from app.db.postgres import engine

def fix_language_enum():
    """Update language values ke format enum yang benar"""
    with engine.connect() as conn:
        # Update language values
        updates = [
            ("UPDATE users SET language = 'ID' WHERE language = 'id' OR language IS NULL"),
            ("UPDATE users SET language = 'EN' WHERE language = 'en'"),
            ("UPDATE users SET language = 'SU' WHERE language = 'su'"),
        ]
        
        for update_sql in updates:
            try:
                conn.execute(text(update_sql))
                conn.commit()
                print(f"✓ {update_sql[:50]}...")
            except Exception as e:
                print(f"✗ Error: {e}")
                conn.rollback()
        
        # Verify
        result = conn.execute(text("SELECT id, email, language FROM users"))
        rows = result.fetchall()
        print(f"\n✅ Updated {len(rows)} users")
        print("\nSample users:")
        for row in rows[:5]:
            print(f"  ID: {row[0]}, Email: {row[1]}, Language: {row[2]}")

if __name__ == "__main__":
    fix_language_enum()

