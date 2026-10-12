"""Build the File PDF (artwork only) and the Die PDF (strokes + model labels).

Colour rule: images go in exactly as supplied. No CMYK conversion, no resampling,
no OutputIntent, and no ICC profile unless the source file carries one itself.

RIP-safe structure, matching the team's Illustrator exports: PDF 1.6, all page
boxes set, labels as vector outlines (no fonts to embed or substitute), and the
Die PDF carries the artwork on a hidden layer with the die on a visible layer.
"""

import zlib
from pathlib import Path

import pikepdf
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from pikepdf import Array, Dictionary, Name
from PIL import Image

from .layout import BED_H, BED_W, GAP_X, LABEL_OFFSET

Image.MAX_IMAGE_PIXELS = None

PDF_VERSION = "1.6"
LABEL_SIZE = 10
STROKE_W = 0.75
_FONT = TTFont(Path(__file__).resolve().parent / "fonts" / "OpenSans-Regular.ttf")
_GLYPHS = _FONT.getGlyphSet()
_CMAP = _FONT.getBestCmap()
_UPM = _FONT["head"].unitsPerEm


class _PdfPathPen(BasePen):
    """Collects glyph outlines as PDF path operators, scaled and positioned."""

    def __init__(self, scale, x0, y0):
        super().__init__(_GLYPHS)
        self.ops, self.s, self.x0, self.y0 = [], scale, x0, y0

    def _pt(self, p):
        return f"{self.x0 + p[0] * self.s:.3f} {self.y0 + p[1] * self.s:.3f}"

    def _moveTo(self, p):
        self.ops.append(f"{self._pt(p)} m")

    def _lineTo(self, p):
        self.ops.append(f"{self._pt(p)} l")

    def _curveToOne(self, p1, p2, p3):
        self.ops.append(f"{self._pt(p1)} {self._pt(p2)} {self._pt(p3)} c")

    def _closePath(self):
        self.ops.append("h")


def _text_outline(text, cx, baseline, size=LABEL_SIZE, max_w=None):
    """Text centred on cx as filled outlines (like Illustrator's Create Outlines).
    max_w: shrink the text (never below 4 pt) so it is no wider than this."""
    names = [_CMAP.get(ord(c), ".notdef") for c in text]
    scale = size / _UPM
    width = sum(_GLYPHS[n].width for n in names) * scale
    if max_w and width > max_w:
        scale *= max(max_w / width, 4 / size)
        width = sum(_GLYPHS[n].width for n in names) * scale
    x, ops = cx - width / 2, []
    for n in names:
        pen = _PdfPathPen(scale, x, baseline)
        _GLYPHS[n].draw(pen)
        ops += pen.ops
        x += _GLYPHS[n].width * scale
    return " ".join(ops) + " f" if ops else ""


def _icc_stream(pdf, icc, n):
    s = pikepdf.Stream(pdf, zlib.compress(icc))
    s.Filter = Name.FlateDecode
    s.N = n
    return Array([Name.ICCBased, s])


def _image_xobject(pdf, path):
    """Embed one image without changing its colour data."""
    with Image.open(path) as im:
        fmt = im.format
        icc = im.info.get("icc_profile")
        mode = im.mode

        if fmt == "JPEG" and mode in ("RGB", "L", "CMYK"):
            # JPEG goes in byte-for-byte.
            raw = open(path, "rb").read()
            n = {"RGB": 3, "L": 1, "CMYK": 4}[mode]
            device = {"RGB": Name.DeviceRGB, "L": Name.DeviceGray, "CMYK": Name.DeviceCMYK}[mode]
            xo = pikepdf.Stream(pdf, raw)
            xo.Type, xo.Subtype = Name.XObject, Name.Image
            xo.Width, xo.Height, xo.BitsPerComponent = im.width, im.height, 8
            xo.Filter = Name.DCTDecode
            xo.ColorSpace = _icc_stream(pdf, icc, n) if icc else device
            if mode == "CMYK" and "adobe" in im.info:
                xo.Decode = Array([1, 0] * 4)  # Adobe-inverted CMYK JPEG
            return xo

        # Lossless formats: unpack pixels, keep colour values untouched.
        if mode == "P":
            im = im.convert("RGBA" if "transparency" in im.info else "RGB")
        elif mode in ("I;16", "I;16B", "I"):
            im = im.convert("L")
        elif mode == "PA":
            im = im.convert("RGBA")
        elif mode == "1":
            im = im.convert("L")
        mode = im.mode

        alpha = None
        if mode in ("RGBA", "LA"):
            alpha = im.getchannel("A")
            im = im.convert("RGB" if mode == "RGBA" else "L")  # drops alpha only
            mode = im.mode
        if alpha is not None and alpha.getextrema() == (255, 255):
            alpha = None  # fully opaque, no mask needed

        n = {"RGB": 3, "L": 1, "CMYK": 4}[mode]
        device = {"RGB": Name.DeviceRGB, "L": Name.DeviceGray, "CMYK": Name.DeviceCMYK}[mode]
        xo = pikepdf.Stream(pdf, zlib.compress(im.tobytes(), 6))
        xo.Type, xo.Subtype = Name.XObject, Name.Image
        xo.Width, xo.Height, xo.BitsPerComponent = im.width, im.height, 8
        xo.Filter = Name.FlateDecode
        xo.ColorSpace = _icc_stream(pdf, icc, n) if icc else device
        if alpha is not None:
            sm = pikepdf.Stream(pdf, zlib.compress(alpha.tobytes(), 6))
            sm.Type, sm.Subtype = Name.XObject, Name.Image
            sm.Width, sm.Height, sm.BitsPerComponent = alpha.width, alpha.height, 8
            sm.ColorSpace, sm.Filter = Name.DeviceGray, Name.FlateDecode
            xo.SMask = sm
        return xo


def _label_ops(p, text):
    return _text_outline(text, p.x + p.w / 2, p.y + p.h + LABEL_OFFSET, max_w=p.w + GAP_X * 0.8)


def _new_pdf(title):
    pdf = pikepdf.new()
    with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
        meta["dc:title"] = title
    pdf.docinfo[Name.Title] = title
    pdf.docinfo[Name.Creator] = "MT3 UV Mix Batch"
    return pdf


FRAME_OPS = f"q 0 {BED_H} {BED_W} -{BED_H} re W n q /GSFrame gs /FmFrame Do Q Q"


def _frame(pdf, resources):
    """Invisible artboard frame, copied from the team's Illustrator PDFs.

    A 0.75 pt stroke round the whole bed at 0% opacity. It prints nothing, but
    Photoshop's "Crop To: Bounding Box" and the RIP see artwork edge to edge, so
    the file always opens at the full 2180 x 1220 mm instead of shrinking to
    the pieces.
    """
    gs = pdf.make_indirect(Dictionary(Type=Name.ExtGState, CA=0, ca=0, BM=Name.Normal,
                                      SMask=Name("/None"), AIS=False, SA=True))
    form = pikepdf.Stream(pdf, (
        f"q 0 {BED_H} {BED_W} -{BED_H} re W n 0 0 0 1 K 0.75 w 10 M 0 j 0 J [] 0 d "
        f"/GSFrame gs 0 {BED_H} {BED_W} -{BED_H} re S Q").encode())
    form.Type, form.Subtype = Name.XObject, Name.Form
    form.BBox = Array([-0.375, -0.375, BED_W + 0.375, BED_H + 0.375])
    form.Group = Dictionary(Type=Name.Group, S=Name.Transparency, I=False, K=False)
    form.Resources = Dictionary(ExtGState=Dictionary(GSFrame=gs))
    for key in (Name.ExtGState, Name.XObject):
        if key not in resources:
            resources[key] = Dictionary()
    resources.ExtGState[Name("/GSFrame")] = gs
    resources.XObject[Name("/FmFrame")] = pdf.make_indirect(form)
    return resources


def _add_page(pdf, ops, resources):
    resources = _frame(pdf, resources)
    ops = [FRAME_OPS] + ops
    box = Array([0, 0, BED_W, BED_H])
    page = pikepdf.Page(Dictionary(
        Type=Name.Page,
        MediaBox=box, CropBox=box, BleedBox=box, TrimBox=box, ArtBox=box,
        Contents=pdf.make_stream("\n".join(ops).encode("latin-1")),
        Resources=resources,
    ))
    pdf.pages.append(page)


def _place_images(pdf, placements, pieces, sheet, xobjs, res_x):
    """Image placement ops for one sheet; repeated files embed once per PDF."""
    ops = []
    for p in (q for q in placements if q.sheet == sheet):
        src = str(pieces[p.index]["path"])
        if src not in xobjs:
            xobjs[src] = (f"Im{len(xobjs)}", pdf.make_indirect(_image_xobject(pdf, src)))
        name, xo = xobjs[src]
        res_x[Name("/" + name)] = xo
        ops.append(f"q {p.w:.4f} 0 0 {p.h:.4f} {p.x:.4f} {p.y:.4f} cm /{name} Do Q")
    return ops


def _layers(pdf, names_on_off):
    """Illustrator-style layers. names_on_off: [(name, visible)] -> list of OCG objects."""
    ocgs = [pdf.make_indirect(Dictionary(Type=Name.OCG, Name=pikepdf.String(n),
                                         Intent=Array([Name.View, Name.Design]))) for n, _ in names_on_off]
    pdf.Root.OCProperties = Dictionary(
        OCGs=Array(ocgs),
        D=Dictionary(ON=Array([o for o, (_, v) in zip(ocgs, names_on_off) if v]),
                     OFF=Array([o for o, (_, v) in zip(ocgs, names_on_off) if not v]),
                     Order=Array(ocgs), RBGroups=Array()),
    )
    return ocgs


def build_pdfs(placements, pieces, file_path, die_path, title):
    """pieces[i] needs: path, label. Writes the File and Die PDFs (spot is a PSD, see psd_build)."""
    sheets = sorted({p.sheet for p in placements})

    # File PDF: artwork only, no labels
    pdf = _new_pdf(title + " FILE")
    xobjs = {}
    for s in sheets:
        res_x = Dictionary()
        ops = _place_images(pdf, placements, pieces, s, xobjs, res_x)
        _add_page(pdf, ops, Dictionary(XObject=res_x))
    pdf.save(file_path, min_version=PDF_VERSION)

    # Die PDF: hidden "Artwork" layer (for reference, like the team's Layer 1)
    # + visible "Die" layer with the strokes and model labels.
    die = _new_pdf(title + " DIE")
    art_ocg, die_ocg = _layers(die, [("Artwork", False), ("Die", True)])
    xobjs = {}
    for s in sheets:
        res_x = Dictionary()
        art = _place_images(die, placements, pieces, s, xobjs, res_x)
        cut = [f"{STROKE_W} w 0 0 0 1 K 0 0 0 1 k"]
        for p in (q for q in placements if q.sheet == s):
            cut.append(f"{p.x:.4f} {p.y:.4f} {p.w:.4f} {p.h:.4f} re S")
            cut.append(_label_ops(p, pieces[p.index]["label"]))
        ops = (["/OC /MC0 BDC"] + art + ["EMC", "/OC /MC1 BDC", "q"] + cut + ["Q", "EMC"])
        _add_page(die, ops, Dictionary(XObject=res_x, Properties=Dictionary(MC0=art_ocg, MC1=die_ocg)))
    die.save(die_path, min_version=PDF_VERSION)
