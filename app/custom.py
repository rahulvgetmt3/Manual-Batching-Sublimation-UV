"""Custom artwork for Sublimation: files uploaded from the computer or fetched from a link,
placed on sheets without any Pulse order.

Each upload is stored in the file cache under the key "custom://<sha>.<ext>", so thumbnails,
sizing and the sheet builder treat it exactly like a downloaded Pulse print file.
"""

import hashlib
import io
import os
import re
import urllib.parse
import urllib.request

from PIL import Image

from .fetch import CACHE_DIR, cached_path, image_info
from .layout import MM

Image.MAX_IMAGE_PIXELS = None

ALLOWED = {"PNG": ".png", "JPEG": ".jpg", "TIFF": ".tif", "WEBP": ".webp"}
MAX_BYTES = 300 * 1024 * 1024
LOW_DPI = 150


class CustomError(Exception):
    pass


def _clean_name(name):
    base = os.path.splitext(os.path.basename(name or ""))[0]
    base = re.sub(r"[_]+", " ", base).strip()
    return base[:80] or "Custom artwork"


def save_bytes(data, filename=""):
    """Validate an image and store it in the cache. Returns the item dict for the UI."""
    if not data:
        raise CustomError(f"{filename or 'file'}: empty file")
    if len(data) > MAX_BYTES:
        raise CustomError(f"{filename}: too large (max 300 MB)")
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
        with Image.open(io.BytesIO(data)) as im:
            fmt = im.format
    except Exception:  # noqa: BLE001 - shown to the user
        raise CustomError(f"{filename or 'file'}: not an image. Use PNG, JPG, TIFF or WebP "
                          "(for PDF/AI artwork, export it as PNG or TIFF at 300 DPI)")
    if fmt not in ALLOWED:
        raise CustomError(f"{filename}: {fmt} images are not supported; use PNG, JPG, TIFF or WebP")
    sha = hashlib.sha256(data).hexdigest()[:24]
    key = f"custom://{sha}{ALLOWED[fmt]}"
    path = cached_path(key)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(data)
        tmp.rename(path)
    return item_for(key, _clean_name(filename))


def save_url(url):
    """Download an image from a link (http/https) and store it."""
    u = (url or "").strip()
    p = urllib.parse.urlparse(u)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise CustomError("Paste a full link starting with http:// or https://")
    # Dropbox share links: ask for the file itself instead of the preview page
    if "dropbox.com" in p.netloc:
        u = re.sub(r"([?&])dl=0", r"\1dl=1", u) if "dl=0" in u else u + ("&" if "?" in u else "?") + "dl=1"
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (MT3 Manual Batching)"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read(MAX_BYTES + 1)
    except Exception as e:  # noqa: BLE001 - shown to the user
        raise CustomError(f"Could not download the link ({e})")
    name = os.path.basename(urllib.parse.unquote(p.path)) or "linked artwork"
    try:
        return save_bytes(data, name)
    except CustomError as e:
        raise CustomError(f"{e}. If this is a share page (Google Drive, WeTransfer...), use a direct image link") from None


def item_for(key, name):
    """Item dict in the same shape the UI uses for Pulse items (no order data)."""
    path = cached_path(key)
    info = image_info(path)
    dpi = info["dpi"][0]
    with Image.open(path) as im:
        mode = "CMYK" if im.mode == "CMYK" else "RGB"
    cid = "CUSTOM-" + key.split("//", 1)[1].split(".")[0][:10].upper()
    return {
        "custom": True, "component_barcode": cid, "item_barcode": "", "fetch_url": key,
        "label": name, "name": name, "copies": 1,
        "family": "CUSTOM", "line": "6UP-EXT", "model": "", "batch_imposition": "Custom artwork",
        "print_code": "", "print_sku": "", "batch_number": "", "order_number": "",
        "job_status": "custom", "order_status": "", "item_status": "",
        "w_pt": info["w_pt"], "h_pt": info["h_pt"],
        "w_mm": round(info["w_pt"] / MM, 1), "h_mm": round(info["h_pt"] / MM, 1),
        "px": info["px"], "dpi": dpi, "low_dpi": dpi < LOW_DPI, "mode": mode,
    }
