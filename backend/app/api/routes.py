import logging
import asyncio
import threading
from contextlib import asynccontextmanager
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    Request,
)
from fastapi_limiter import FastAPILimiter
from sqlalchemy.orm import Session
from sqlalchemy import or_, create_engine
from sqlalchemy.orm import sessionmaker
from typing import List, Optional
import json
import uuid
import redis.asyncio as redis

from app.core.config import get_settings, get_default_settings, Settings
from app.core.logging import setup_logging
from app.models.database import init_db, DownloadRecord
from app.models.schemas import (
    VideoInfoRequest,
    VideoInfoResponse,
    DownloadRequest,
    DownloadResponse,
    DownloadRecordResponse,
    RetryDownloadRequest,
    SettingsUpdate,
    SettingsResponse,
)
from app.services.downloader import VideoDownloaderService

setup_logging()
logger = logging.getLogger(__name__)

router = APIRouter()

settings = get_settings()
SessionLocal = init_db(settings.DATABASE_URL)


# 线程安全的服务实例管理
class ThreadSafeDownloaderService:
    """线程安全的下载服务管理器"""

    def __init__(self):
        self._lock = threading.RLock()
        self._service = None
        self._init_service()

    def _init_service(self):
        with self._lock:
            self._service = VideoDownloaderService(
                download_path=settings.DOWNLOAD_PATH,
                proxy_url=settings.PROXY_URL,
                proxy_domains=settings.get_proxy_domains(),
                bilibili_cookies=settings.BILIBILI_COOKIES_FILE,
                bilibili_browser=settings.BILIBILI_BROWSER,
            )

    def update_settings(self, **kwargs):
        """更新设置并重新初始化服务"""
        with self._lock:
            if "download_path" in kwargs:
                settings.DOWNLOAD_PATH = kwargs["download_path"]
            if "proxy_url" in kwargs:
                settings.PROXY_URL = kwargs["proxy_url"]
            if "proxy_domains" in kwargs:
                settings.PROXY_DOMAINS = ",".join(kwargs["proxy_domains"])
            self._init_service()

    def __getattr__(self, name):
        with self._lock:
            return getattr(self._service, name)


# 全局服务实例
downloader_service = ThreadSafeDownloaderService()

# 活动下载管理（带最大限制）
MAX_CONCURRENT_DOWNLOADS = 5
active_downloads = {}
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 初始化限流器
@asynccontextmanager
async def lifespan(app):
    """应用生命周期管理"""
    # 启动时初始化限流器
    try:
        redis_connection = redis.from_url(
            getattr(settings, "REDIS_URL", "redis://localhost:6379"),
            encoding="utf-8",
            decode_responses=True,
        )
        await FastAPILimiter.init(redis_connection)
        logger.info("Rate limiter initialized")
    except Exception as e:
        logger.warning(
            f"Failed to initialize rate limiter: {e}. Running without rate limiting."
        )

    yield

    # 关闭时清理
    logger.info("Shutting down...")


@router.post("/video/info", response_model=VideoInfoResponse)
async def get_video_info(request: VideoInfoRequest, db: Session = Depends(get_db)):
    """获取视频信息"""
    logger.info(f"API: Get video info request - URL: {request.url}")

    # 验证URL
    if not request.url or not request.url.strip():
        raise HTTPException(status_code=422, detail="URL is required")

    url = request.url.strip()

    # 检查数据库中是否已存在
    existing = (
        db.query(DownloadRecord)
        .filter(DownloadRecord.url == url)
        .order_by(DownloadRecord.created_at.desc())
        .first()
    )

    if existing:
        logger.info(
            f"API: Found existing record - ID: {existing.id}, Status: {existing.status}"
        )
        return VideoInfoResponse(
            id=existing.id,
            title=existing.title,
            description=existing.video_info.get("description")
            if existing.video_info
            else None,
            duration=existing.duration,
            uploader=existing.video_info.get("uploader")
            if existing.video_info
            else None,
            thumbnail=existing.video_info.get("thumbnail")
            if existing.video_info
            else None,
            formats=existing.video_info.get("formats", [])
            if existing.video_info
            else [],
            status=existing.status,
        )

    try:
        info = await downloader_service.get_video_info(url)

        # 创建待处理记录
        record = DownloadRecord(
            title=info.get("title", "Unknown"),
            url=url,
            download_path=settings.DOWNLOAD_PATH,
            status="pending",
            duration=info.get("duration"),
            video_info=info,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        logger.info(f"API: Created pending record - ID: {record.id}")

        return VideoInfoResponse(
            id=record.id,
            title=info.get("title", "Unknown"),
            description=info.get("description"),
            duration=info.get("duration"),
            uploader=info.get("uploader"),
            thumbnail=info.get("thumbnail"),
            formats=info.get("formats", []),
            status="pending",
        )
    except ValueError as e:
        logger.warning(f"API: Invalid URL - {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"API: Failed to get video info - Error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch video info: {str(e)}"
        )


@router.post("/video/download", response_model=DownloadResponse)
async def start_download(request: DownloadRequest, db: Session = Depends(get_db)):
    """开始下载"""
    download_id = str(uuid.uuid4())
    logger.info(
        f"API: Start download request - URL: {request.url}, Quality: {request.quality}, Record ID: {request.record_id}"
    )

    # 验证URL
    if not request.url or not request.url.strip():
        raise HTTPException(status_code=422, detail="URL is required")

    # 检查并发限制
    if len(active_downloads) >= MAX_CONCURRENT_DOWNLOADS:
        raise HTTPException(
            status_code=503,
            detail=f"Maximum concurrent downloads ({MAX_CONCURRENT_DOWNLOADS}) reached. Please try again later.",
        )

    # 如果提供了记录ID，更新现有记录
    if request.record_id:
        record = (
            db.query(DownloadRecord)
            .filter(DownloadRecord.id == request.record_id)
            .first()
        )
        if record:
            record.status = "downloading"
            record.quality = request.quality
            db.commit()
            db.refresh(record)
            logger.info(f"API: Updated existing record - ID: {record.id}")
        else:
            # 未找到则创建新记录
            record = DownloadRecord(
                title="Downloading...",
                url=request.url,
                download_path=settings.DOWNLOAD_PATH,
                quality=request.quality,
                status="downloading",
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            logger.info(f"API: Created new record - ID: {record.id}")
    else:
        # 创建新记录
        record = DownloadRecord(
            title="Downloading...",
            url=request.url,
            download_path=settings.DOWNLOAD_PATH,
            quality=request.quality,
            status="downloading",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        logger.info(f"API: Created new record - ID: {record.id}")

    active_downloads[download_id] = {
        "record_id": record.id,
        "progress": 0,
        "status": "downloading",
    }

    # 在后台任务中处理下载
    asyncio.create_task(
        process_download(download_id, request.url, request.quality, record.id)
    )

    return DownloadResponse(
        id=record.id,
        title="Downloading...",
        status="downloading",
        message="Download started",
    )


@router.post("/video/retry", response_model=DownloadResponse)
async def retry_download(request: RetryDownloadRequest, db: Session = Depends(get_db)):
    """重试下载"""
    logger.info(f"API: Retry download request - Record ID: {request.record_id}")

    record = (
        db.query(DownloadRecord).filter(DownloadRecord.id == request.record_id).first()
    )
    if not record:
        logger.warning(f"API: Record not found - ID: {request.record_id}")
        raise HTTPException(status_code=404, detail="Download record not found")

    if record.status not in ["failed", "pending"]:
        logger.warning(f"API: Cannot retry - Status is {record.status}")
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry download with status: {record.status}",
        )

    # 检查并发限制
    if len(active_downloads) >= MAX_CONCURRENT_DOWNLOADS:
        raise HTTPException(
            status_code=503,
            detail=f"Maximum concurrent downloads ({MAX_CONCURRENT_DOWNLOADS}) reached. Please try again later.",
        )

    download_id = str(uuid.uuid4())

    # 更新记录
    record.status = "downloading"
    record.quality = request.quality
    record.error_msg = None
    db.commit()
    db.refresh(record)

    logger.info(f"API: Retrying download - ID: {record.id}, URL: {record.url}")

    active_downloads[download_id] = {
        "record_id": record.id,
        "progress": 0,
        "status": "downloading",
    }

    asyncio.create_task(
        process_download(download_id, record.url, request.quality, record.id)
    )

    return DownloadResponse(
        id=record.id,
        title=record.title,
        status="downloading",
        message="Download retry started",
    )


async def process_download(download_id: str, url: str, quality: str, record_id: int):
    """处理下载任务（后台执行）"""
    logger.info(f"API: Processing download - ID: {download_id}, Record ID: {record_id}")

    # 使用信号量限制并发
    async with download_semaphore:
        # 创建新的数据库会话（后台任务不能使用主请求的会话）
        db = SessionLocal()

        async def progress_callback(d):
            if d.get("status") == "downloading":
                downloaded = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                if total > 0:
                    progress = downloaded / total
                    active_downloads[download_id]["progress"] = progress
                    logger.debug(f"Download {download_id} progress: {progress:.2%}")

        try:
            result = await downloader_service.download(
                url=url,
                quality=quality,
                download_id=download_id,
                progress_callback=progress_callback,
            )

            record = (
                db.query(DownloadRecord).filter(DownloadRecord.id == record_id).first()
            )

            if result.get("success"):
                record.title = result.get("title", "Unknown")
                record.status = "completed"
                record.file_size = result.get("filesize")
                record.duration = result.get("duration")
                record.error_msg = None
                logger.info(
                    f"API: Download completed - ID: {download_id}, File: {result.get('filename')}"
                )
            else:
                record.status = "failed"
                record.error_msg = result.get("error", "Unknown error")
                logger.error(
                    f"API: Download failed - ID: {download_id}, Error: {record.error_msg}"
                )

            db.commit()
            active_downloads[download_id]["status"] = record.status

        except Exception as e:
            logger.error(
                f"API: Exception during download - ID: {download_id}, Error: {e}"
            )
            record = (
                db.query(DownloadRecord).filter(DownloadRecord.id == record_id).first()
            )
            if record:
                record.status = "failed"
                record.error_msg = str(e)
                db.commit()
            active_downloads[download_id]["status"] = "failed"
        finally:
            db.close()
            # 清理活动下载记录（保留一段时间以便查询状态）
            await asyncio.sleep(60)  # 保留1分钟
            if download_id in active_downloads:
                del active_downloads[download_id]


@router.get("/downloads", response_model=List[DownloadRecordResponse])
async def get_downloads(limit: int = 50, db: Session = Depends(get_db)):
    """获取下载历史"""
    logger.info(f"API: Get downloads request - Limit: {limit}")

    # 限制最大返回数量
    if limit > 100:
        limit = 100

    records = (
        db.query(DownloadRecord)
        .order_by(DownloadRecord.created_at.desc())
        .limit(limit)
        .all()
    )
    logger.info(f"API: Returning {len(records)} download records")
    return records


@router.get("/downloads/search")
async def search_downloads(query: str, limit: int = 50, db: Session = Depends(get_db)):
    """搜索下载记录"""
    logger.info(f"API: Search downloads - Query: {query}")

    if not query or not query.strip():
        raise HTTPException(status_code=422, detail="Search query is required")

    # 限制最大返回数量
    if limit > 100:
        limit = 100

    records = (
        db.query(DownloadRecord)
        .filter(
            or_(
                DownloadRecord.title.contains(query), DownloadRecord.url.contains(query)
            )
        )
        .order_by(DownloadRecord.created_at.desc())
        .limit(limit)
        .all()
    )
    logger.info(f"API: Search returned {len(records)} results")
    return records


@router.delete("/downloads/{download_id}")
async def delete_download(download_id: int, db: Session = Depends(get_db)):
    """删除下载记录"""
    logger.info(f"API: Delete download - ID: {download_id}")
    record = db.query(DownloadRecord).filter(DownloadRecord.id == download_id).first()
    if not record:
        logger.warning(f"API: Download not found - ID: {download_id}")
        raise HTTPException(status_code=404, detail="Download not found")

    db.delete(record)
    db.commit()
    logger.info(f"API: Download deleted - ID: {download_id}")
    return {"message": "Download deleted"}


@router.delete("/downloads")
async def clear_downloads(db: Session = Depends(get_db)):
    """清空所有下载记录"""
    logger.info("API: Clear all downloads")
    count = db.query(DownloadRecord).count()
    db.query(DownloadRecord).delete()
    db.commit()
    logger.info(f"API: Cleared {count} download records")
    return {"message": "All downloads cleared", "count": count}


@router.get("/settings", response_model=SettingsResponse)
async def get_settings_endpoint():
    """获取设置"""
    logger.info("API: Get settings")
    default_settings = get_default_settings()
    return SettingsResponse(
        download_path=settings.DOWNLOAD_PATH,
        proxy_url=settings.PROXY_URL,
        proxy_domains=settings.get_proxy_domains(),
        default_proxy_url=default_settings.PROXY_URL,
        default_proxy_domains=default_settings.get_proxy_domains(),
    )


@router.put("/settings")
async def update_settings(settings_update: SettingsUpdate):
    """更新设置"""
    global downloader_service

    logger.info(f"API: Update settings - {settings_update}")

    update_kwargs = {}
    if settings_update.download_path:
        update_kwargs["download_path"] = settings_update.download_path
    if settings_update.proxy_url is not None:
        update_kwargs["proxy_url"] = settings_update.proxy_url
    if settings_update.proxy_domains is not None:
        update_kwargs["proxy_domains"] = settings_update.proxy_domains

    # 使用线程安全的方法更新
    downloader_service.update_settings(**update_kwargs)

    logger.info("API: Settings updated successfully")
    return SettingsResponse(
        download_path=settings.DOWNLOAD_PATH,
        proxy_url=settings.PROXY_URL,
        proxy_domains=settings.get_proxy_domains(),
        default_proxy_url=settings.PROXY_URL,
        default_proxy_domains=settings.get_proxy_domains(),
    )


@router.websocket("/ws/download/{download_id}")
async def download_websocket(websocket: WebSocket, download_id: str):
    """WebSocket 连接获取下载进度"""
    logger.info(f"API: WebSocket connection - Download ID: {download_id}")
    await websocket.accept()

    try:
        while True:
            if download_id in active_downloads:
                data = active_downloads[download_id].copy()

                progress_data = downloader_service.get_progress(download_id)
                if progress_data:
                    downloaded = progress_data.get("downloaded_bytes", 0)
                    total = progress_data.get("total_bytes") or progress_data.get(
                        "total_bytes_estimate", 0
                    )
                    if total > 0:
                        data["progress"] = downloaded / total
                    data["speed"] = progress_data.get("speed", 0)
                    data["eta"] = progress_data.get("eta", 0)

                await websocket.send_json(data)

                if data["status"] in ["completed", "failed"]:
                    logger.info(
                        f"API: WebSocket closing - Download {download_id} finished with status: {data['status']}"
                    )
                    break
            else:
                # 下载记录不存在，返回未找到
                await websocket.send_json({"status": "not_found", "progress": 0})
                break

            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        logger.info(f"API: WebSocket disconnected - Download ID: {download_id}")
    except Exception as e:
        logger.error(f"API: WebSocket error - Download ID: {download_id}, Error: {e}")
        try:
            await websocket.close()
        except:
            pass
