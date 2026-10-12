"""Sublimation sheets: artwork placed mirrored and centred in the 6UP / 6UP Extended
templates, with the "OrderID-Model-CaseType" name beside each piece.

Rules (agreed with Rahul, 2026-10-12):
- Template backgrounds come from the team's .ai files, cleaned by tools/build_sub_templates.py.
- 6 slots per sheet, filled TL, TR, ML, MR, BL, BR. Each sheet is a separate PDF.
- Artwork is placed at its true size (pixels / DPI, normally 300), centred in the slot and
  mirrored horizontally by default (a toggle allows non-flipped sheets). Mirroring is done by
  the placement matrix; pixels are never changed.
- The name goes beside each piece, reading bottom to top: left-column pieces on the left edge
  and right-column pieces on the right edge, centred on the slot, 15 pt black, as vector
  outlines, so it never depends on fonts. Positions are taken from the team's reference.
- Colour (artwork only): "RGB" keeps RGB files untouched and converts CMYK files to RGB;
  "CMYK" keeps CMYK files untouched and converts RGB files to CMYK. Conversions use the
  team's 'U.S. Web Coated (SWOP) v2' profile with sRGB, relative colorimetric + black point
  compensation. Converted images carry NO profile. Untouched files are embedded exactly
  as with UV.
"""

import io
import json
import zlib
from pathlib import Path

import pikepdf
from pikepdf import Array, Dictionary, Name
from PIL import Image, ImageCms

from .pdf_build import _GLYPHS, _CMAP, _UPM, _PdfPathPen, _image_xobject

Image.MAX_IMAGE_PIXELS = None

TPL_DIR = Path(__file__).resolve().parent / "templates" / "sublimation"
TEMPLATES = json.loads((TPL_DIR / "templates.json").read_text(encoding="utf-8"))
SLOTS_PER_SHEET = 6
MM = 72 / 25.4
NAME_SIZE = 15.08            # pt, as in the team's reference
NAME_X_LEFT = 12.3 * MM      # baseline x for left-column names (reference)
NAME_X_RIGHT = 310.3 * MM    # baseline x for right-column names (reference)
NAME_MARGIN = 6 * MM         # keep names this far inside the slot height
MARK_CLEAR = 3 * MM          # keep names this far from registration marks

_SRGB = ImageCms.createProfile("sRGB")
_SWOP = ImageCms.ImageCmsProfile(str(TPL_DIR / "swop.icc"))
_FLAGS = ImageCms.Flags.BLACKPOINTCOMPENSATION
_INTENT = ImageCms.Intent.RELATIVE_COLORIMETRIC


def template_title(key):
    return TEMPLATES[key]["title"]


def image_mode(path):
    with Image.open(path) as im:
        return "CMYK" if im.mode == "CMYK" else "RGB"


def _src_profile(im, default):
    icc = im.info.get("icc_profile")
    if icc:
        try:
            return ImageCms.ImageCmsProfile(io.BytesIO(icc))
        except Exception:  # noqa: BLE001 - broken embedded profile: fall back
            pass
    return default


def _flate_image(pdf, data, w, h, cs, smask=None):
    xo = pikepdf.Stream(pdf, zlib.compress(data, 6))
    xo.Type, xo.Subtype = Name.XObject, Name.Image
    xo.Width, xo.Height, xo.BitsPerComponent = w, h, 8
    xo.ColorSpace, xo.Filter = cs, Name.FlateDecode
    if smask is not None:
        xo.SMask = smask
    return xo


def _converted_xobject(pdf, path, target):
    """Convert to target ('RGB' or 'CMYK') with SWOP/sRGB; no profile embedded."""
    with Image.open(path) as im:
        im.load()
        alpha = None
        if im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info):
            rgba = im.convert("RGBA")
            alpha = rgba.getchannel("A")
            src = rgba.convert("RGB")
        elif im.mode == "CMYK":
            src = im
        else:
            src = im.convert("RGB")
        if target == "CMYK":
            out = ImageCms.profileToProfile(src, _src_profile(im, _SRGB), _SWOP, renderingIntent=_INTENT,
                                            outputMode="CMYK", flags=_FLAGS)
            cs = Name.DeviceCMYK
        else:
            out = ImageCms.profileToProfile(src, _src_profile(im, _SWOP), _SRGB, renderingIntent=_INTENT,
                                            outputMode="RGB", flags=_FLAGS)
            cs = Name.DeviceRGB
    smask = None
    if alpha is not None and alpha.getextrema() != (255, 255):
        smask = pdf.make_indirect(_flate_image(pdf, alpha.tobytes(), alpha.width, alpha.height, Name.DeviceGray))
    return _flate_image(pdf, out.tobytes(), out.width, out.height, cs, smask)


def artwork_xobject(pdf, path, color):
    """Untouched when the file is already in the chosen mode, else converted."""
    if image_mode(path) == color:
        return _image_xobject(pdf, str(path)), False
    return _converted_xobject(pdf, path, color), True


def _name_span(slot_y0, slot_y1, marks, width):
    """Where the name goes along the slot: centred if that clears the registration marks on that edge,
    otherwise centred in the largest clear stretch of the slot (shrunk only if it cannot fit).
    Returns (start_y, length)."""
    lo, hi = slot_y0 + NAME_MARGIN, slot_y1 - NAME_MARGIN
    free = [(lo, hi)]
    for m0, m1 in marks:
        m0, m1 = m0 - MARK_CLEAR, m1 + MARK_CLEAR
        nxt = []
        for a, b in free:
            if m1 <= a or m0 >= b:
                nxt.append((a, b))
            else:
                if m0 > a:
                    nxt.append((a, m0))
                if m1 < b:
                    nxt.append((m1, b))
        free = nxt
    cy = (slot_y0 + slot_y1) / 2
    c0, c1 = cy - width / 2, cy + width / 2
    if any(a <= c0 and c1 <= b for a, b in free):
        return c0, width
    a, b = max(free, key=lambda seg: seg[1] - seg[0])
    length = min(width, b - a)
    return (a + b) / 2 - length / 2, length


def _name_outline(text, x_baseline, slot_y0, slot_y1, marks):
    """Text rotated 90 degrees (reads bottom to top) beside a slot, as filled outlines."""
    names = [_CMAP.get(ord(c), ".notdef") for c in text]
    width = sum(_GLYPHS[n].width for n in names) * NAME_SIZE / _UPM
    start, length = _name_span(slot_y0, slot_y1, marks, width)
    scale = NAME_SIZE / _UPM * (length / width)   # shrinks only when the name cannot fit
    ops, x = [], 0.0
    for n in names:  # glyphs laid out along +x from 0, then rotated into place by the cm below
        pen = _PdfPathPen(scale, x, 0)
        _GLYPHS[n].draw(pen)
        ops += pen.ops
        x += _GLYPHS[n].width * scale
    return f"q 0 1 -1 0 {x_baseline:.3f} {start:.3f} cm " + " ".join(ops) + " f Q"


def build_sheet(template, color, pieces, out_path, title, mirror=True):
    """pieces: up to 6 dicts {path, w_pt, h_pt, name}; written in slot order TL..BR.
    Returns a list of warnings (artwork larger than its slot)."""
    tpl = TEMPLATES[template]
    src = pikepdf.open(TPL_DIR / f"{template}.pdf")
    pdf = pikepdf.new()
    pdf.pages.append(src.pages[0])
    if "/OCProperties" in src.Root:
        pdf.Root.OCProperties = pdf.copy_foreign(src.make_indirect(src.Root.OCProperties))
    page = pdf.pages[0]
    pdf.docinfo[Name.Title] = title
    pdf.docinfo[Name.Creator] = "MT3 Manual Batching"

    res = page.Resources
    if Name.XObject not in res:
        res.XObject = Dictionary()
    ops, warnings, cache = ["0 0 0 1 k"], [], {}
    for i, pc in enumerate(pieces[:SLOTS_PER_SHEET]):
        sx, sy, sw, sh = tpl["slots"][i]
        key = str(pc["path"])
        if key not in cache:
            xo, _ = artwork_xobject(pdf, pc["path"], color)
            cache[key] = (f"SubIm{len(cache)}", pdf.make_indirect(xo))
        name, xo = cache[key]
        res.XObject[Name("/" + name)] = xo
        w, h = pc["w_pt"], pc["h_pt"]
        cx, cy = sx + sw / 2, sy + sh / 2
        x0, y0 = cx - w / 2, cy - h / 2
        if w > sw + 0.5 or h > sh + 0.5:
            warnings.append(f"slot {i + 1}: artwork {w / MM:.1f} x {h / MM:.1f} mm is larger than the slot "
                            f"{sw / MM:.1f} x {sh / MM:.1f} mm")
        if mirror:  # flipped horizontally: x scale negative, origin on the right edge
            ops.append(f"q {-w:.4f} 0 0 {h:.4f} {x0 + w:.4f} {y0:.4f} cm /{name} Do Q")
        else:
            ops.append(f"q {w:.4f} 0 0 {h:.4f} {x0:.4f} {y0:.4f} cm /{name} Do Q")
        side = "L" if i % 2 == 0 else "R"
        x_base = NAME_X_LEFT if side == "L" else NAME_X_RIGHT
        marks = [(m0, m1) for sd, m0, m1 in tpl.get("marks", []) if sd == side]
        ops.append(_name_outline(pc["name"], x_base, sy, sy + sh, marks))
    page.contents_add(pdf.make_stream(("\n".join(ops)).encode("latin-1")), prepend=False)
    pdf.save(out_path, min_version="1.6")
    return warnings
