import logging
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import uuid
import asyncio

from app.core.config import get_settings, get_default_settings, Settings
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

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

router = APIRouter()

settings = get_settings()
SessionLocal = init_db(settings.DATABASE_URL)

downloader_service = VideoDownloaderService(
    download_path=settings.DOWNLOAD_PATH,
    proxy_url=settings.PROXY_URL,
    proxy_domains=settings.get_proxy_domains(),
    bilibili_cookies=settings.BILIBILI_COOKIES_FILE,
    bilibili_browser=settings.BILIBILI_BROWSER,
)

active_downloads = {}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/video/info", response_model=VideoInfoResponse)
async def get_video_info(request: VideoInfoRequest, db: Session = Depends(get_db)):
    logger.info(f"API: Get video info request - URL: {request.url}")

    # Check if URL already exists
    existing = (
        db.query(DownloadRecord)
        .filter(DownloadRecord.url == request.url)
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
        info = await downloader_service.get_video_info(request.url)

        # Create pending record
        record = DownloadRecord(
            title=info.get("title", "Unknown"),
            url=request.url,
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
    except Exception as e:
        logger.error(f"API: Failed to get video info - Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/video/download", response_model=DownloadResponse)
async def start_download(request: DownloadRequest, db: Session = Depends(get_db)):
    download_id = str(uuid.uuid4())
    logger.info(
        f"API: Start download request - URL: {request.url}, Quality: {request.quality}, Record ID: {request.record_id}"
    )

    # If record_id provided, update existing record
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
            # Create new record if not found
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
        # Create new record
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

    download_id = str(uuid.uuid4())

    # Update record
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
    logger.info(f"API: Processing download - ID: {download_id}, Record ID: {record_id}")
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

        record = db.query(DownloadRecord).filter(DownloadRecord.id == record_id).first()

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
        logger.error(f"API: Exception during download - ID: {download_id}, Error: {e}")
        record = db.query(DownloadRecord).filter(DownloadRecord.id == record_id).first()
        record.status = "failed"
        record.error_msg = str(e)
        db.commit()
        active_downloads[download_id]["status"] = "failed"
    finally:
        db.close()


@router.get("/downloads", response_model=List[DownloadRecordResponse])
async def get_downloads(limit: int = 50, db: Session = Depends(get_db)):
    logger.info(f"API: Get downloads request - Limit: {limit}")
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
    logger.info(f"API: Search downloads - Query: {query}")
    from sqlalchemy import or_

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
    logger.info("API: Clear all downloads")
    count = db.query(DownloadRecord).count()
    db.query(DownloadRecord).delete()
    db.commit()
    logger.info(f"API: Cleared {count} download records")
    return {"message": "All downloads cleared"}


@router.get("/settings", response_model=SettingsResponse)
async def get_settings_endpoint():
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
    global downloader_service

    logger.info(f"API: Update settings - {settings_update}")

    if settings_update.download_path:
        settings.DOWNLOAD_PATH = settings_update.download_path
    if settings_update.proxy_url is not None:
        settings.PROXY_URL = settings_update.proxy_url
    if settings_update.proxy_domains is not None:
        settings.PROXY_DOMAINS = ",".join(settings_update.proxy_domains)

    downloader_service = VideoDownloaderService(
        download_path=settings.DOWNLOAD_PATH,
        proxy_url=settings.PROXY_URL,
        proxy_domains=settings.get_proxy_domains(),
        bilibili_cookies=settings.BILIBILI_COOKIES_FILE,
        bilibili_browser=settings.BILIBILI_BROWSER,
    )

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
    logger.info(f"API: WebSocket connection - Download ID: {download_id}")
    await websocket.accept()

    try:
        while True:
            if download_id in active_downloads:
                data = active_downloads[download_id]

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

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        logger.info(f"API: WebSocket disconnected - Download ID: {download_id}")
