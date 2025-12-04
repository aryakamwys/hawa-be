#!/usr/bin/env python3
"""Script to create an admin user in the database.

Usage:
    poetry run python scripts/create_admin.py --email admin@example.com --password secure_password --full-name "Admin Name"
    
    Or if dependencies are installed in your environment:
    poetry run python scripts/create_admin.py --email admin@hawa.com --password hawa --full-name "Admin Hawa"

Make sure DATABASE_URL is set in your .env file or environment variables.
"""

import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file if it exists
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

try:
    from sqlalchemy.orm import Session
    from app.db.postgres import SessionLocal
    from app.db.models.user import User, RoleEnum
    from app.core.security import hash_password
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("\nMake sure you have installed all dependencies:")
    print("  poetry install")
    print("\nOr run the script with poetry:")
    print("  poetry run python scripts/create_admin.py ...")
    sys.exit(1)
except ValueError as e:
    if "DATABASE_URL" in str(e):
        print(f"Error: {e}")
        print("\nPlease set DATABASE_URL in your .env file or as an environment variable.")
        print("Example: DATABASE_URL=postgresql://user:password@localhost/dbname")
        sys.exit(1)
    raise


def create_admin_user(email: str, password: str, full_name: str | None = None):
    """Create or promote a user to admin role."""
    db: Session = SessionLocal()
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"User with email {email} already exists!")
            if existing_user.role == RoleEnum.ADMIN:
                print("User is already an admin.")
            else:
                existing_user.role = RoleEnum.ADMIN
                db.commit()
                db.refresh(existing_user)
                print(f"User {email} promoted to admin.")
            return existing_user
        
        # Create new admin user
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=RoleEnum.ADMIN,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Admin user created successfully: {email}")
        return user
    except Exception as e:
        db.rollback()
        print(f"Error creating admin user: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Create an admin user")
    parser.add_argument("--email", required=True, help="Admin email")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--full-name", help="Admin full name")
    args = parser.parse_args()
    
    create_admin_user(args.email, args.password, args.full_name)

