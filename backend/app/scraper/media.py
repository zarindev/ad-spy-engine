"""Ad card screenshots and media downloads (size-limited, best effort)."""

from __future__ import annotations

import logging
import mimetypes
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.paths import data_dir, media_dir, slugify

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


def competitor_media_dir(competitor: str) -> Path:
    path = media_dir() / slugify(competitor)
    path.mkdir(parents=True, exist_ok=True)
    return path


def relative_to_data(path: Path) -> str:
    return path.resolve().relative_to(data_dir().resolve()).as_posix()


def _extension(url: str, content_type: str | None) -> str:
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if ext:
            return ".jpg" if ext in {".jpe", ".jpeg"} else ext
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4"} else ".bin"


def download_file(client: httpx.Client, url: str, dest_stem: Path, max_bytes: int) -> Path | None:
    """Stream a file to disk, aborting if it exceeds max_bytes. Returns the saved path."""
    try:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            declared = int(resp.headers.get("content-length") or 0)
            if declared and declared > max_bytes:
                log.info("Skipping %s (%.1f MB > limit)", dest_stem.name, declared / 1e6)
                return None
            dest = dest_stem.with_suffix(_extension(url, resp.headers.get("content-type")))
            size = 0
            tmp = dest.with_suffix(dest.suffix + ".part")
            with tmp.open("wb") as fh:
                for chunk in resp.iter_bytes(65536):
                    size += len(chunk)
                    if size > max_bytes:
                        fh.close()
                        tmp.unlink(missing_ok=True)
                        log.info("Aborted %s: exceeded size limit", dest_stem.name)
                        return None
                    fh.write(chunk)
            tmp.replace(dest)
            return dest
    except (httpx.HTTPError, OSError) as exc:
        log.warning("Download failed for %s: %s", dest_stem.name, exc)
        return None


class MediaDownloader:
    """Downloads media on a small thread pool so scrolling never waits on the network."""

    def __init__(self, competitor: str, workers: int = 4, max_mb: float = 25) -> None:
        self.folder = competitor_media_dir(competitor)
        self.max_bytes = int(max_mb * 1_000_000)
        self.client = httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="media")

    def submit(self, url: str, stem: str) -> Future[Path | None]:
        return self.pool.submit(download_file, self.client, url, self.folder / stem, self.max_bytes)

    def close(self) -> None:
        self.pool.shutdown(wait=True)
        self.client.close()

    def __enter__(self) -> MediaDownloader:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
