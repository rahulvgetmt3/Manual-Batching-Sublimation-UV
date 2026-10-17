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
  outlines, so it never depends on fonts (any readable font is fine - Rahul). Centred on the
  slot and allowed to cross the registration marks (Rahul, 2026-10-12).
- Colour (artwork only): "RGB" keeps RGB files untouched and converts CMYK files to RGB;
  "CMYK" keeps CMYK files untouched and converts RGB files to CMYK. Conversions use the
  team's 'U.S. Web Coated (SWOP) v2' profile with sRGB, relative colorimetric + black point
  compensation. Converted images carry NO profile. Untouched files are embedded exactly
  as with UV.
"""

import io
import zlib

import pikepdf
from pikepdf import Array, Dictionary, Name
from PIL import Image, ImageCms

from .labels import text_outline
from .pdf_build import _GLYPHS, _CMAP, _UPM, _PdfPathPen, _image_xobject
from .layout import MM
from .sub_templates import BUILTIN_DIR, NAME_SIZE

Image.MAX_IMAGE_PIXELS = None

NAME_MARGIN = 6 * MM         # keep names this far inside the slot height

# Sheet batch number: red, just right of the colour bar, like SiteFlow prints its batch ID (Rahul, 2026-10-16).
BATCH_SIZE = 22              # pt
BATCH_RED = "0 1 1 0 k"      # CMYK red
# Built-in templates: (x where the colour bar ends, distance from the page top to the bar's bottom), in pt.
BATCH_AT = {"6UP": (566.0, 34.4), "6UP-EXT": (560.0, 37.4)}

_SRGB = ImageCms.createProfile("sRGB")
_SWOP = ImageCms.ImageCmsProfile(str(BUILTIN_DIR / "swop.icc"))
_FLAGS = ImageCms.Flags.BLACKPOINTCOMPENSATION
_INTENT = ImageCms.Intent.RELATIVE_COLORIMETRIC


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


def artwork_xobject(pdf, path, color, mode=None):
    """Untouched when the file is already in the chosen mode, else converted."""
    if (mode or image_mode(path)) == color:
        return _image_xobject(pdf, str(path))
    return _converted_xobject(pdf, path, color)


class ArtCache:
    """Each artwork decoded / converted / compressed once per batch; sheets copy the finished stream
    (pikepdf copies the compressed bytes as they are). Holds one scratch PDF for the batch."""

    def __init__(self, color):
        self.color, self.pdf, self.xobjects = color, pikepdf.new(), {}

    def get(self, piece):
        key = str(piece["path"])
        if key not in self.xobjects:
            xo = artwork_xobject(self.pdf, piece["path"], self.color, piece.get("src_mode"))
            self.xobjects[key] = self.pdf.make_indirect(xo)
        return self.xobjects[key]


def _name_outline(text, x_baseline, slot_y0, slot_y1):
    """Text rotated 90 degrees (reads bottom to top) beside a slot, as filled outlines.
    Centred on the slot; it may cross the registration marks (as in the team's file). It only
    shrinks if the name is longer than the slot."""
    names = [_CMAP.get(ord(c), ".notdef") for c in text]
    width = sum(_GLYPHS[n].width for n in names) * NAME_SIZE / _UPM
    length = min(width, (slot_y1 - slot_y0) - 2 * NAME_MARGIN)
    start = (slot_y0 + slot_y1) / 2 - length / 2
    scale = NAME_SIZE / _UPM * (length / width)   # shrinks only when the name cannot fit
    ops, x = [], 0.0
    for n in names:  # glyphs laid out along +x from 0, then rotated into place by the cm below
        pen = _PdfPathPen(scale, x, 0)
        _GLYPHS[n].draw(pen)
        ops += pen.ops
        x += _GLYPHS[n].width * scale
    return f"q 0 1 -1 0 {x_baseline:.3f} {start:.3f} cm " + " ".join(ops) + " f Q"


def _batch_number(tpl, text):
    """The sheet's batch number in red. Built-in templates: just right of the colour bar, sitting on
    its baseline. Uploaded templates: top right, right-aligned to the slots, in the gap above them."""
    page_w, page_h = tpl["page"]
    if tpl.get("builtin") and tpl.get("key") in BATCH_AT:
        x, from_top = BATCH_AT[tpl["key"]]
        return f"{BATCH_RED} " + text_outline(text, x + 6, page_h - from_top, BATCH_SIZE)
    top = max(sy + sh for _, sy, _, sh in tpl["slots"])
    right = max(sx + sw for sx, _, sw, _ in tpl["slots"])
    size = max(6.0, min(BATCH_SIZE, (page_h - top) * 0.6))
    return f"{BATCH_RED} " + text_outline(text, right, top + (page_h - top - size * 0.72) / 2, size, align="right")


def build_sheet(tpl, color, pieces, out_path, title, mirror=True, art=None, batch=None):
    """tpl: a template from registry(). pieces: up to one per slot, dicts {path, w_pt, h_pt, name};
    filled in slot order (top row first, left to right). art: the batch's ArtCache (one is made if
    not given). batch: the sheet's batch number, printed in red at the top. Returns a list of
    warnings (artwork larger than its slot)."""
    art = art or ArtCache(color)
    with pikepdf.open(tpl["pdf"]) as src:   # kept open until saved: page content is copied lazily
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
        ops, warnings, names = ["0 0 0 1 k"], [], {}
        for i, pc in enumerate(pieces[:len(tpl["slots"])]):
            sx, sy, sw, sh = tpl["slots"][i]
            key = str(pc["path"])
            if key not in names:
                names[key] = f"SubIm{len(names)}"
                res.XObject[Name("/" + names[key])] = pdf.copy_foreign(art.get(pc))
            name = names[key]
            w, h = pc["w_pt"], pc["h_pt"]
            if pc.get("fit"):  # custom artwork: scale proportionally to fit the slot (never stretched)
                k = min(sw / w, sh / h)
                w, h = w * k, h * k
            cx, cy = sx + sw / 2, sy + sh / 2
            x0, y0 = cx - w / 2, cy - h / 2
            if w > sw + 0.5 or h > sh + 0.5:
                warnings.append(f"slot {i + 1}: artwork {w / MM:.1f} x {h / MM:.1f} mm is larger than the slot "
                                f"{sw / MM:.1f} x {sh / MM:.1f} mm")
            if mirror:  # flipped horizontally: x scale negative, origin on the right edge
                ops.append(f"q {-w:.4f} 0 0 {h:.4f} {x0 + w:.4f} {y0:.4f} cm /{name} Do Q")
            else:
                ops.append(f"q {w:.4f} 0 0 {h:.4f} {x0:.4f} {y0:.4f} cm /{name} Do Q")
            ops.append(_name_outline(pc["name"], tpl["names"][i]["x"], sy, sy + sh))
        if batch:
            ops.append(_batch_number(tpl, batch))
        page.contents_add(pdf.make_stream(("\n".join(ops)).encode("latin-1")), prepend=False)
        pdf.save(out_path, min_version="1.6")
    return warnings
