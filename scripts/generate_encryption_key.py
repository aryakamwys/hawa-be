#!/usr/bin/env python3
"""
Script untuk generate encryption key untuk ENCRYPTION_KEY di .env
Jalankan: poetry run python scripts/generate_encryption_key.py
"""
from cryptography.fernet import Fernet

if __name__ == "__main__":
    key = Fernet.generate_key()
    print("=" * 60)
    print("ENCRYPTION_KEY untuk .env file:")
    print("=" * 60)
    print(key.decode())
    print("=" * 60)
    print("\nTambahkan ke .env file:")
    print(f"ENCRYPTION_KEY={key.decode()}")

