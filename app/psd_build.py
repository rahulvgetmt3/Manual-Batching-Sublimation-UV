"""Spot file as a Photoshop PSD: RGB layers + a "Spot Color 1" spot channel.

Photoshop flattens any ordinary PDF on open, so a PDF cannot carry the spot channel
into Photoshop. A PSD opens with the channel every time; the team then saves or
sends from Photoshop as before.

Document: 2180.76 x 1221.23 mm at 300 ppi (25757 x 14424 px), RGB, 8-bit.
  - One layer per piece, holding the original pixels and transparency at the same
    right-aligned position as the File / Die PDFs (no resampling at 300 dpi).
  - Spot channel "Spot Color 1" = artwork opacity: full ink where the file is
    opaque, soft on anti-aliased edges, none where a PNG is transparent.
The composite stored for other apps is plain white (as with Photoshop's
"Maximize Compatibility" off); Photoshop builds the picture from the layers.
"""

import io
import os
import struct

import numpy as np
from PIL import Image

from .layout import BED_H

Image.MAX_IMAGE_PIXELS = None

PPI = 300
DOC_W = 25757  # 2180.76 mm, same as the team's file
DOC_H = 14424  # 1221.23 mm
SPOT_NAME = os.environ.get("SPOT_NAME", "Spot Color 1")


def _packbits_rows(arr):
    """PackBits (PSD RLE) per row via libtiff. Returns (row byte counts, data)."""
    h, w = arr.shape
    buf = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(arr), "L").save(buf, "TIFF", compression="packbits", strip_size=w)
    buf.seek(0)
    tags = Image.open(buf).tag_v2
    offsets, counts = tags[273], tags[279]
    raw = buf.getbuffer()
    data = b"".join(bytes(raw[o:o + c]) for o, c in zip(offsets, counts))
    return list(counts), data


def _rle_channel(arr):
    """Channel image data block: compression=1, row counts, packed rows."""
    counts, data = _packbits_rows(arr)
    return struct.pack(">H", 1) + struct.pack(f">{len(counts)}H", *counts) + data


def _pascal(s, pad):
    b = s.encode("latin-1", "replace")[:255]
    out = bytes([len(b)]) + b
    return out + b"\0" * (-len(out) % pad)


def _resource(rid, data):
    return b"8BIM" + struct.pack(">H", rid) + b"\0\0" + struct.pack(">I", len(data)) + data + (b"\0" if len(data) % 2 else b"")


def _image_resources():
    name = SPOT_NAME
    res = _resource(1005, struct.pack(">IHHIHH", PPI << 16, 1, 2, PPI << 16, 1, 2))  # 300 ppi
    res += _resource(1006, _pascal(name, 1))  # alpha/spot channel names
    uni = (name + "\0").encode("utf-16-be")
    res += _resource(1045, struct.pack(">I", len(name) + 1) + uni)
    white = struct.pack(">H4H", 0, 65535, 65535, 65535, 0)  # RGB preview colour
    res += _resource(1007, white + struct.pack(">HBB", 100, 2, 0))  # kind 2 = spot
    res += _resource(1077, struct.pack(">I", 1) + white + struct.pack(">HB", 100, 2))
    return res


def _piece_pixels(path, w_px, h_px):
    """(rgb HxWx3, alpha HxW) uint8 exactly as in the file; resampled only if not 300 dpi."""
    with Image.open(path) as im:
        if im.mode in ("P", "PA"):
            im = im.convert("RGBA" if ("transparency" in im.info or im.mode == "PA") else "RGB")
        elif im.mode in ("I;16", "I;16B", "I", "1"):
            im = im.convert("L")
        if im.mode == "LA":
            im = im.convert("RGBA")
        if im.mode == "L":
            im = im.convert("RGB")
        if im.mode == "CMYK":
            im = im.convert("RGB")  # PSD here is RGB; CMYK print files are not expected
        if im.size != (w_px, h_px):
            im = im.resize((w_px, h_px), Image.LANCZOS)
        if im.mode == "RGBA":
            arr = np.asarray(im)
            return arr[:, :, :3], arr[:, :, 3]
        rgb = np.asarray(im.convert("RGB"))
        return rgb, np.full(rgb.shape[:2], 255, np.uint8)


def build_spot_psd(placements, pieces, items, out_path):
    """Write one PSD for one sheet's placements."""
    layers = []  # (top, left, bottom, right, name, [(id, blob)])
    spot = np.zeros((DOC_H, DOC_W), np.uint8)
    for p in placements:
        w_px = round(p.w / 72 * PPI)
        h_px = round(p.h / 72 * PPI)
        left = round(p.x / 72 * PPI)
        top = round((BED_H - (p.y + p.h)) / 72 * PPI)
        left = min(max(left, 0), DOC_W - w_px)
        top = min(max(top, 0), DOC_H - h_px)
        rgb, alpha = _piece_pixels(pieces[p.index]["path"], w_px, h_px)
        spot[top:top + h_px, left:left + w_px] = np.maximum(spot[top:top + h_px, left:left + w_px], alpha)
        it = items[p.index]
        name = f"{p.position:03d} {it.label} {it.component_barcode}"
        chans = [(-1, _rle_channel(alpha))] + [(c, _rle_channel(rgb[:, :, c])) for c in range(3)]
        layers.append((top, left, top + h_px, left + w_px, name, chans))

    with open(out_path, "wb") as f:
        # Header: RGB + 1 spot channel
        f.write(b"8BPS" + struct.pack(">H6xHIIHH", 1, 4, DOC_H, DOC_W, 8, 3))
        f.write(struct.pack(">I", 0))  # colour mode data
        res = _image_resources()
        f.write(struct.pack(">I", len(res)) + res)

        # Layer and mask information (records first, then every channel's data)
        recs = [struct.pack(">h", len(layers))]
        for top, left, bottom, right, name, chans in layers:
            r = struct.pack(">iiiiH", top, left, bottom, right, len(chans))
            for cid, blob in chans:
                r += struct.pack(">hI", cid, len(blob))
            r += b"8BIMnorm" + struct.pack(">BBBB", 255, 0, 0x08, 0)
            extra = struct.pack(">II", 0, 0) + _pascal(name, 4)
            recs.append(r + struct.pack(">I", len(extra)) + extra)
        info_len = sum(map(len, recs)) + sum(len(b) for *_, chans in layers for _, b in chans)
        pad = -info_len % 4
        f.write(struct.pack(">I", 4 + info_len + pad + 4))  # section length
        f.write(struct.pack(">I", info_len + pad))           # layer info length
        for r in recs:
            f.write(r)
        for *_, chans in layers:
            for _, blob in chans:
                f.write(blob)
        f.write(b"\0" * pad + struct.pack(">I", 0))          # empty global layer mask

        # Merged image data: white composite (R, G, B) + the spot channel
        white_counts, white_row = _packbits_rows(np.full((1, DOC_W), 255, np.uint8))
        # Photoshop stores spot channels inverted: 0 (black) = full ink, 255 (white) = none.
        spot_counts, spot_data = _packbits_rows(255 - spot)
        f.write(struct.pack(">H", 1))
        f.write(struct.pack(">H", white_counts[0]) * (3 * DOC_H))
        f.write(struct.pack(f">{DOC_H}H", *spot_counts))
        for _ in range(3):
            f.write(white_row * DOC_H)
        f.write(spot_data)
