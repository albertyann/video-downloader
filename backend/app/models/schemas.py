from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
from datetime import datetime


class VideoInfoRequest(BaseModel):
    url: str


class VideoInfoResponse(BaseModel):
    id: Optional[int] = None
    title: str
    description: Optional[str] = None
    duration: Optional[float] = None
    uploader: Optional[str] = None
    thumbnail: Optional[str] = None
    formats: List[dict] = []
    status: str = "pending"


class DownloadRequest(BaseModel):
    url: str
    quality: str = "best"
    record_id: Optional[int] = None


class DownloadResponse(BaseModel):
    id: int
    title: str
    status: str
    message: str


class DownloadRecordResponse(BaseModel):
    id: int
    title: str
    url: str
    download_path: str
    file_size: Optional[int]
    duration: Optional[float]
    quality: Optional[str]
    status: str
    error_msg: Optional[str]
    video_info: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class RetryDownloadRequest(BaseModel):
    record_id: int
    quality: str = "best"


class SettingsUpdate(BaseModel):
    download_path: Optional[str] = None
    proxy_url: Optional[str] = None
    proxy_domains: Optional[List[str]] = None


class SettingsResponse(BaseModel):
    download_path: str
    proxy_url: str
    proxy_domains: List[str]
    default_proxy_url: str = ""
    default_proxy_domains: List[str] = []
