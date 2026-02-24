import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.routes import router
from app.core.logging import setup_logging

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="Video downloader with domain-specific proxy support",
    version="1.0.0",
)

# CORS 配置 - 生产环境应该限制具体的 origin
origins = settings.get_cors_origins()
if settings.DEBUG:
    # 开发环境允许所有来源
    allow_origins = ["*"]
else:
    # 生产环境使用配置的 origin
    allow_origins = (
        origins if origins else ["http://localhost:5173", "http://localhost:3000"]
    )
    # 如果仍然包含通配符，发出警告
    if "*" in allow_origins:
        logger.warning(
            "CORS is configured to allow all origins in production. This is insecure!"
        )

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    expose_headers=["Content-Disposition"],
    max_age=600,  # 预检请求缓存10分钟
)

app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Video Downloader API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "download_path": settings.DOWNLOAD_PATH,
        "debug": settings.DEBUG,
    }


@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("Video Downloader API Starting...")
    logger.info(f"Download path: {settings.DOWNLOAD_PATH}")
    logger.info(f"Proxy URL: {settings.PROXY_URL}")
    logger.info(f"Proxy domains: {settings.get_proxy_domains()}")
    logger.info(f"API docs: http://{settings.HOST}:{settings.PORT}/docs")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"CORS origins: {allow_origins}")
    logger.info("=" * 60)


# Uvicorn 启动命令:
# cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
