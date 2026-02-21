import os
from typing import List
from pydantic import field_validator
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
    PROXY_DOMAINS: str = "youtube.com,youtu.be,bilibili.com,b23.tv"

    # Bilibili settings
    BILIBILI_COOKIES_FILE: str = ""
    BILIBILI_BROWSER: str = ""

    # Database
    DATABASE_URL: str = "sqlite:///./downloads.db"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    class Config:
        env_file = ".env"
        case_sensitive = True

    def get_proxy_domains(self) -> List[str]:
        return [item.strip() for item in self.PROXY_DOMAINS.split(",") if item.strip()]

    def get_cors_origins(self) -> List[str]:
        return [item.strip() for item in self.CORS_ORIGINS.split(",") if item.strip()]


@lru_cache()
def get_settings():
    return Settings()


def get_default_settings():
    return Settings()
