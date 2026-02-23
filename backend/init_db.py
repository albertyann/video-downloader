#!/usr/bin/env python3
import os
import sys

backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.core.config import get_settings
from app.models.database import init_db


def main():
    settings = get_settings()
    print("=" * 60)
    print("Video Downloader Database Initialization")
    print("=" * 60)
    database_url = settings.DATABASE_URL
    print(f"Database URL: {database_url}")
    if database_url.startswith("sqlite:///"):
        if database_url.startswith("sqlite:///./"):
            db_file = os.path.join(
                backend_dir, database_url.replace("sqlite:///./", "")
            )
        elif database_url.startswith("sqlite:///"):
            db_file = database_url.replace("sqlite:///", "/")
        else:
            db_file = database_url.replace("sqlite://", "")
    else:
        print(f"Error: Unsupported database type: {database_url}")
        sys.exit(1)

    print(f"Database file path: {db_file}")
    if os.path.exists(db_file):
        print(f"\nWarning: Database file already exists: {db_file}")
        response = input("Recreate? (y/N): ").strip().lower()
        if response == "y":
            backup_file = f"{db_file}.backup"
            print(f"Backing up to: {backup_file}")
            os.rename(db_file, backup_file)
        else:
            print("Cancelled")
            sys.exit(0)

    db_dir = os.path.dirname(db_file)
    if db_dir and not os.path.exists(db_dir):
        print(f"Creating directory: {db_dir}")
        os.makedirs(db_dir, exist_ok=True)

    print("\nCreating database tables...")
    try:
        SessionLocal = init_db(database_url)
        print("✓ Database tables created successfully!")
        db = SessionLocal()
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db.close()
        print("✓ Database connection test passed!")

        print(f"\nDatabase file: {db_file}")
        print("=" * 60)
        print("Database initialization completed!")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ Database initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
