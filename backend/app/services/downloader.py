import os
import asyncio
import logging
from typing import Optional, Callable, Dict, Any, List
from yt_dlp import YoutubeDL
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if ":" in domain:
            domain = domain.split(":")[0]
        if domain.startswith("www."):
            domain = domain[4:]
        elif domain.startswith("m."):
            domain = domain[2:]
        return domain
    except Exception:
        return ""


def is_bilibili(url: str) -> bool:
    domain = extract_domain(url)
    return "bilibili" in domain or domain == "b23.tv"


def build_ytdlp_command(url: str, ydl_opts: Dict[str, Any]) -> str:
    cmd_parts = ["yt-dlp"]
    
    if ydl_opts.get("format"):
        cmd_parts.append(f'-f "{ydl_opts["format"]}"')
    
    if ydl_opts.get("proxy"):
        cmd_parts.append(f'--proxy "{ydl_opts["proxy"]}"')
    
    if ydl_opts.get("outtmpl"):
        cmd_parts.append(f'-o "{ydl_opts["outtmpl"]}"')
    
    if ydl_opts.get("cookiesfrombrowser"):
        cmd_parts.append(f'--cookies-from-browser "{ydl_opts["cookiesfrombrowser"]}"')
    elif ydl_opts.get("cookiefile"):
        cmd_parts.append(f'--cookies "{ydl_opts["cookiefile"]}"')
    
    if ydl_opts.get("referer"):
        cmd_parts.append(f'--referer "{ydl_opts["referer"]}"')
    
    if ydl_opts.get("headers"):
        for header_name, header_value in ydl_opts["headers"].items():
            cmd_parts.append(f'--add-header "{header_name}:{header_value}"')
    
    if ydl_opts.get("quiet"):
        cmd_parts.append("--quiet")
    
    cmd_parts.append(f'"{url}"')
    
    return " ".join(cmd_parts)


class VideoDownloaderService:
    def __init__(self, download_path: str, proxy_url: str = "", proxy_domains: List[str] = None, 
                 bilibili_cookies: str = None, bilibili_browser: str = None):
        self.download_path = download_path
        self.proxy_url = proxy_url
        self.proxy_domains = proxy_domains or []
        self.bilibili_cookies = bilibili_cookies
        self.bilibili_browser = bilibili_browser
        self._progress_callbacks = {}
        self._progress_data = {}
        
        os.makedirs(download_path, exist_ok=True)
        
        logger.info(f"VideoDownloaderService initialized")
        logger.info(f"Download path: {download_path}")
        logger.info(f"Proxy URL: {proxy_url}")
        logger.info(f"Proxy domains: {proxy_domains}")
        logger.info(f"Bilibili cookies file: {bilibili_cookies}")
        logger.info(f"Bilibili browser: {bilibili_browser}")
    
    def _get_proxy_for_url(self, url: str) -> Optional[str]:
        domain = extract_domain(url)
        if not self.proxy_url or not self.proxy_domains:
            return None
        
        for pd in self.proxy_domains:
            if domain == pd or domain.endswith("." + pd):
                logger.info(f"Proxy matched for domain: {domain} -> using proxy")
                return self.proxy_url
        
        logger.info(f"No proxy for domain: {domain} -> direct connection")
        return None
    
    def _get_bilibili_options(self, url: str) -> Dict[str, Any]:
        """Get bilibili-specific download options"""
        opts = {}
        
        if not is_bilibili(url):
            return opts
        
        logger.info(f"Bilibili URL detected: {url}")
        
        # Add referer for bilibili
        opts["referer"] = "https://www.bilibili.com"
        
        # Add custom headers
        opts["headers"] = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.bilibili.com/"
        }
        
        # Add cookies if configured
        if self.bilibili_cookies and os.path.exists(self.bilibili_cookies):
            opts["cookiefile"] = self.bilibili_cookies
            logger.info(f"Using cookies file: {self.bilibili_cookies}")
        elif self.bilibili_browser:
            opts["cookiesfrombrowser"] = self.bilibili_browser
            logger.info(f"Using cookies from browser: {self.bilibili_browser}")
        
        # Extractor args for bilibili
        opts["extractor_args"] = {
            "bilibili": {
                "try_look": "1"  # Try to get 720p/1080p without login
            }
        }
        
        return opts
    
    def _create_progress_hook(self, download_id: str):
        def hook(d: Dict[str, Any]):
            self._progress_data[download_id] = d
            logger.debug(f"Progress update for {download_id}: {d.get('status')}")
        return hook
    
    def get_progress(self, download_id: str) -> Optional[Dict[str, Any]]:
        return self._progress_data.get(download_id)
    
    async def get_video_info(self, url: str) -> Dict[str, Any]:
        logger.info(f"Fetching video info for URL: {url}")
        
        proxy = self._get_proxy_for_url(url)
        bilibili_opts = self._get_bilibili_options(url)
        
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }
        
        if proxy:
            ydl_opts["proxy"] = proxy
        
        # Merge bilibili options
        ydl_opts.update(bilibili_opts)
        
        cmd = build_ytdlp_command(url, ydl_opts)
        logger.info(f"Command: {cmd}")
        
        loop = asyncio.get_event_loop()
        
        def extract():
            with YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        try:
            info = await loop.run_in_executor(None, extract)
            logger.info(f"Successfully fetched info: {info.get('title', 'Unknown')}")
        except Exception as e:
            logger.error(f"Failed to fetch video info: {e}")
            raise
        
        formats = []
        for f in info.get("formats", []):
            if f.get("vcodec") != "none" and f.get("acodec") != "none":
                formats.append({
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution", "unknown"),
                    "filesize": f.get("filesize") or f.get("filesize_approx"),
                    "quality": f.get("quality", 0),
                    "format_note": f.get("format_note", ""),
                })
        
        formats.sort(key=lambda x: x.get("quality", 0), reverse=True)
        
        return {
            "title": info.get("title", "Unknown"),
            "description": info.get("description", ""),
            "duration": info.get("duration"),
            "uploader": info.get("uploader", "Unknown"),
            "thumbnail": info.get("thumbnail"),
            "formats": formats,
            "is_bilibili": is_bilibili(url),
        }
    
    async def download(
        self,
        url: str,
        quality: str = "best",
        download_id: str = None,
        progress_callback: Callable = None
    ) -> Dict[str, Any]:
        logger.info(f"Starting download - URL: {url}, Quality: {quality}, ID: {download_id}")
        
        if download_id and progress_callback:
            self._progress_callbacks[download_id] = progress_callback
        
        proxy = self._get_proxy_for_url(url)
        bilibili_opts = self._get_bilibili_options(url)
        
        if quality in ["best", "worst"]:
            format_str = quality
        elif quality.endswith("p"):
            height = quality[:-1]
            format_str = f"best[height<={height}]"
        else:
            format_str = quality
        
        ydl_opts = {
            "format": format_str,
            "outtmpl": os.path.join(self.download_path, "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }
        
        if proxy:
            ydl_opts["proxy"] = proxy
        
        # Merge bilibili options
        ydl_opts.update(bilibili_opts)
        
        if download_id:
            ydl_opts["progress_hooks"] = [self._create_progress_hook(download_id)]
        
        cmd = build_ytdlp_command(url, ydl_opts)
        logger.info(f"Download command: {cmd}")
        
        loop = asyncio.get_event_loop()
        
        def do_download():
            logger.info(f"Executing download for: {url}")
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                result = {
                    "success": True,
                    "title": info.get("title"),
                    "filename": os.path.basename(filename),
                    "filepath": os.path.join(self.download_path, filename),
                    "duration": info.get("duration"),
                    "filesize": info.get("filesize") or info.get("filesize_approx"),
                }
                logger.info(f"Download completed: {result['filename']}")
                return result
        
        try:
            result = await loop.run_in_executor(None, do_download)
            logger.info(f"Download successful: {result.get('title')}")
            return result
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            if download_id:
                if download_id in self._progress_callbacks:
                    del self._progress_callbacks[download_id]
                if download_id in self._progress_data:
                    del self._progress_data[download_id]
    
    def get_available_qualities(self, video_info: Dict[str, Any]) -> List[Dict[str, str]]:
        qualities = [{"display": "Best Quality", "value": "best"}]
        formats = video_info.get("formats", [])
        
        seen_resolutions = set()
        
        for fmt in formats:
            resolution = fmt.get("resolution", "")
            if resolution and "x" in resolution:
                height = resolution.split("x")[1]
                res_key = f"{height}p"
                if res_key not in seen_resolutions:
                    seen_resolutions.add(res_key)
                    qualities.append({
                        "display": f"{res_key} ({fmt.get('ext', 'unknown')})",
                        "value": res_key,
                    })
        
        qualities.append({"display": "Worst Quality", "value": "worst"})
        return qualities
