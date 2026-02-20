import os
from typing import List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "Video Downloader"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DOWNLOAD_PATH: str = os.path.expanduser("~/Downloads/VideoDownloader")
    
    # Proxy settings
    PROXY_URL: str = ""
    PROXY_DOMAINS: List[str] = ["youtube.com", "youtu.be", "bilibili.com", "b23.tv"]
    
    # Bilibili settings
    BILIBILI_COOKIES_FILE: str = ""  # Path to cookies.txt file
    BILIBILI_BROWSER: str = ""  # Browser name for cookies (chrome, firefox, edge, etc.)
    
    # Database
    DATABASE_URL: str = "sqlite:///./downloads.db"
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings():
    return Settings()
