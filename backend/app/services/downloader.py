import os
import asyncio
import logging
import re
import shlex
from typing import Optional, Callable, Dict, Any, List
from yt_dlp import YoutubeDL
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，防止路径遍历和非法字符
    """
    if not filename:
        return "unknown"

    # 替换危险字符
    filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
    # 移除控制字符
    filename = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", filename)
    # 移除路径遍历
    filename = filename.replace("..", "_")
    # 移除前导/尾随点和空格
    filename = filename.strip(". ")
    # 限制长度
    if len(filename) > 200:
        filename = filename[:200]

    return filename or "unknown"


def build_ytdlp_command(url: str, ydl_opts: Dict[str, Any]) -> str:
    """
    构建 yt-dlp 命令字符串（仅用于日志记录，不实际执行）
    所有值都经过 shlex.quote 转义以防止命令注入
    """
    cmd_parts = ["yt-dlp"]

    if ydl_opts.get("format"):
        cmd_parts.append(f"-f {shlex.quote(ydl_opts['format'])}")

    if ydl_opts.get("proxy"):
        cmd_parts.append(f"--proxy {shlex.quote(ydl_opts['proxy'])}")

    if ydl_opts.get("outtmpl"):
        cmd_parts.append(f"-o {shlex.quote(ydl_opts['outtmpl'])}")

    if ydl_opts.get("cookiesfrombrowser"):
        cmd_parts.append(
            f"--cookies-from-browser {shlex.quote(ydl_opts['cookiesfrombrowser'])}"
        )
    elif ydl_opts.get("cookiefile"):
        cmd_parts.append(f"--cookies {shlex.quote(ydl_opts['cookiefile'])}")

    if ydl_opts.get("referer"):
        cmd_parts.append(f"--referer {shlex.quote(ydl_opts['referer'])}")

    if ydl_opts.get("headers"):
        for header_name, header_value in ydl_opts["headers"].items():
            cmd_parts.append(
                f"--add-header {shlex.quote(f'{header_name}:{header_value}')}"
            )

    if ydl_opts.get("quiet"):
        cmd_parts.append("--quiet")

    # URL 也需要转义
    cmd_parts.append(shlex.quote(url))

    return " ".join(cmd_parts)


class VideoDownloaderService:
    def __init__(
        self,
        download_path: str,
        proxy_url: str = "",
        proxy_domains: List[str] = None,
        bilibili_cookies: str = None,
        bilibili_browser: str = None,
    ):
        self.download_path = download_path
        self.proxy_url = proxy_url
        self.proxy_domains = proxy_domains or []
        self.bilibili_cookies = bilibili_cookies
        self.bilibili_browser = bilibili_browser
        self._progress_callbacks = {}
        self._progress_data = {}

        # 确保下载路径存在且安全
        self._validate_and_create_download_path()

        logger.info(f"VideoDownloaderService initialized")
        logger.info(f"Download path: {download_path}")
        logger.info(f"Proxy URL: {proxy_url}")
        logger.info(f"Proxy domains: {proxy_domains}")
        logger.info(f"Bilibili cookies file: {bilibili_cookies}")
        logger.info(f"Bilibili browser: {bilibili_browser}")

    def _validate_and_create_download_path(self):
        """验证并创建下载路径"""
        # 解析真实路径
        real_path = os.path.realpath(os.path.expanduser(self.download_path))

        # 确保路径不是系统关键目录
        system_paths = [
            "/bin",
            "/sbin",
            "/usr",
            "/etc",
            "/lib",
            "/lib64",
            "/boot",
            "/dev",
        ]
        for sys_path in system_paths:
            if real_path.startswith(sys_path):
                raise ValueError(
                    f"Download path cannot be a system directory: {real_path}"
                )

        # 创建目录
        os.makedirs(real_path, exist_ok=True)

        # 验证目录可写
        if not os.access(real_path, os.W_OK):
            raise PermissionError(f"Download path is not writable: {real_path}")

        # 更新为解析后的路径
        self.download_path = real_path

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
            "Referer": "https://www.bilibili.com/",
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

        # 验证 URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
            if parsed.scheme not in ["http", "https"]:
                raise ValueError("URL must use http or https protocol")
        except Exception as e:
            raise ValueError(f"Invalid URL: {e}")

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

        # 安全地记录命令（仅用于调试）
        cmd = build_ytdlp_command(url, ydl_opts)
        logger.debug(f"Command (for reference only): {cmd}")

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
                formats.append(
                    {
                        "format_id": f.get("format_id"),
                        "ext": f.get("ext"),
                        "resolution": f.get("resolution", "unknown"),
                        "filesize": f.get("filesize") or f.get("filesize_approx"),
                        "quality": f.get("quality", 0),
                        "format_note": f.get("format_note", ""),
                    }
                )

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
        progress_callback: Callable = None,
    ) -> Dict[str, Any]:
        logger.info(
            f"Starting download - URL: {url}, Quality: {quality}, ID: {download_id}"
        )

        if download_id and progress_callback:
            self._progress_callbacks[download_id] = progress_callback

        # 验证 URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
            if parsed.scheme not in ["http", "https"]:
                raise ValueError("URL must use http or https protocol")
        except Exception as e:
            return {
                "success": False,
                "error": f"Invalid URL: {e}",
            }

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
            "quiet": True,
            "no_warnings": True,
        }

        if proxy:
            ydl_opts["proxy"] = proxy

        # Merge bilibili options
        ydl_opts.update(bilibili_opts)

        if download_id:
            ydl_opts["progress_hooks"] = [self._create_progress_hook(download_id)]

        # 安全地记录命令（仅用于调试）
        cmd = build_ytdlp_command(url, ydl_opts)
        logger.debug(f"Download command (for reference only): {cmd}")

        loop = asyncio.get_event_loop()

        def do_download():
            logger.info(f"Executing download for: {url}")
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

                # 安全地获取文件名
                raw_title = info.get("title", "unknown")
                safe_title = sanitize_filename(raw_title)

                # 构建安全的输出路径
                ext = info.get("ext", "mp4")
                filename = f"{safe_title}.{ext}"
                filepath = os.path.join(self.download_path, filename)

                # 验证文件路径安全
                real_filepath = os.path.realpath(filepath)
                if not real_filepath.startswith(self.download_path):
                    raise SecurityError(f"Path traversal detected: {filepath}")

                result = {
                    "success": True,
                    "title": safe_title,
                    "filename": filename,
                    "filepath": real_filepath,
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

    def get_available_qualities(
        self, video_info: Dict[str, Any]
    ) -> List[Dict[str, str]]:
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
                    qualities.append(
                        {
                            "display": f"{res_key} ({fmt.get('ext', 'unknown')})",
                            "value": res_key,
                        }
                    )

        qualities.append({"display": "Worst Quality", "value": "worst"})
        return qualities


class SecurityError(Exception):
    """安全相关错误"""

    pass
