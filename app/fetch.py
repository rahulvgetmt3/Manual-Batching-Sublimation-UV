"""Download MT3 print files into a local cache and read their physical size."""

import hashlib
import os
import urllib.request
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

CACHE_DIR = Path(os.environ.get("CACHE_DIR", Path(__file__).resolve().parent.parent / "data" / "cache"))
DEFAULT_DPI = 300.0


def cached_path(url):
    ext = os.path.splitext(url.split("?")[0])[1].lower() or ".bin"
    return CACHE_DIR / (hashlib.sha256(url.encode()).hexdigest()[:24] + ext)


def cached_file(url):
    """Return a local path for url, downloading it once."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cached_path(url)
    if not path.exists():
        tmp = path.with_suffix(path.suffix + ".part")
        req = urllib.request.Request(url, headers={"User-Agent": "mt3-uv-mix/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        tmp.rename(path)
    return path


def _clean_dpi(d):
    """PNG stores DPI as px/metre, so 300 comes back as 299.9994; snap it."""
    try:
        d = float(d)
    except (TypeError, ValueError):
        return DEFAULT_DPI
    if d <= 1:
        return DEFAULT_DPI
    return float(round(d)) if abs(d - round(d)) < 0.05 else d


def image_info(path):
    """Pixel size, DPI and physical size in points (1 pt = 1/72 in)."""
    with Image.open(path) as im:
        w, h = im.size
        dpi = im.info.get("dpi") or (DEFAULT_DPI, DEFAULT_DPI)
        fmt = im.format
        mode = "CMYK" if im.mode == "CMYK" else "RGB"
    dx, dy = (_clean_dpi(d) for d in dpi[:2])
    return {
        "format": fmt,
        "mode": mode,
        "px": (w, h),
        "dpi": (dx, dy),
        "w_pt": w / dx * 72.0,
        "h_pt": h / dy * 72.0,
    }
