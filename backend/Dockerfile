# Backend Dockerfile for FastAPI
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for yt-dlp
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create downloads directory
RUN mkdir -p /downloads

# Initialize database (non-interactive, auto-create if not exists)
RUN python -c "
import os
import sys
sys.path.insert(0, '/app')
from app.core.config import get_settings
from app.models.database import init_db

settings = get_settings()
database_url = settings.DATABASE_URL

if database_url.startswith('sqlite:///'):
    if database_url.startswith('sqlite:///./'):
        db_file = database_url.replace('sqlite:///./', '/app/')
    else:
        db_file = database_url.replace('sqlite:///', '/')
    
    db_dir = os.path.dirname(db_file)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    print(f'Initializing database at: {db_file}')
    SessionLocal = init_db(database_url)
    db = SessionLocal()
    from sqlalchemy import text
    db.execute(text('SELECT 1'))
    db.close()
    print('✓ Database initialized successfully')
else:
    print(f'Warning: Non-SQLite database: {database_url}')
    print('Skipping database initialization (should be handled externally)')
"

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
