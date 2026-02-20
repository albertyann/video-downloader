import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="Video downloader with domain-specific proxy support",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Video Downloader API", "version": "1.0.0"}


@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("Video Downloader API Starting...")
    logger.info(f"Download path: {settings.DOWNLOAD_PATH}")
    logger.info(f"Proxy URL: {settings.PROXY_URL}")
    logger.info(f"Proxy domains: {settings.PROXY_DOMAINS}")
    logger.info(f"API docs: http://{settings.HOST}:{settings.PORT}/docs")
    logger.info("=" * 60)


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
