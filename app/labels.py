"""Item labels for Sublimation sheets: one 2 x 1 inch label per piece, one PDF per sheet
(one label per page, in slot order). It's a copy of the live HP SiteFlow greensheet template
"Greensheet Manifest Label Testing - MB 2x1" (id 69b18e120d31c7276a7b583b), whose item page is:

    #5482032 | GetCasely | POD-KDL-511          order number | From | Code
    AMAZON 7" KINDLE PAPERWHITE KINDLE          Description (upper case, wraps)
    ---------------------------------------------------------------- divider
    MULTI-2                                     Item                 [QR = component barcode]
    Maegan Marie                                Customer Name         item barcode text
    QTY 1 / 1

All values come from Pulse (source_id, source, hp_od_code, description, item_type,
ship_to_name, component/item barcodes, quantity). The design is 1132 x 566 px, scaled onto
144 x 72 pt. Text is drawn as vector outlines (Open Sans Bold/Semibold standing in for Calibri) and
the QR as vector modules, so it prints sharp on a label printer with no fonts needed.
"""

from pathlib import Path

import pikepdf
import segno
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from pikepdf import Array, Dictionary, Name

PAGE_W, PAGE_H = 144.0, 72.0          # 2 x 1 inch
DESIGN_W, DESIGN_H = 1132.0, 566.0    # SiteFlow template px
K = PAGE_W / DESIGN_W                 # pt per template px
PAD_T, PAD_R, PAD_B, PAD_L = 15, 30, 15, 18
RIGHT_COL = 195                       # px, QR column width
QR_PX = 180

FROM_NAMES = {  # Pulse source -> SiteFlow 'From' attribute, read from live orders (2026-10-12)
    "getcasely": "GetCasely", "fumicase": "FumiCase", "inprintwetrust": "Inprintwetrust",
    "casely": "casely", "hp.mt3": "hp.mt3", "iclick": "iClick", "arenacases": "ArenaCases",
    "onotone": "Onotone",
}

_FONT_DIR = Path(__file__).resolve().parent / "fonts"
_FONTS = {}


def _font(weight):
    """'black' (900) -> Open Sans Bold, 'bold' (700) -> Open Sans Semibold."""
    name = {"black": "OpenSans-Bold.ttf", "bold": "OpenSans-Semibold.ttf"}[weight]
    if name not in _FONTS:
        f = TTFont(_FONT_DIR / name)
        _FONTS[name] = (f.getGlyphSet(), f.getBestCmap(), f["head"].unitsPerEm)
    return _FONTS[name]


class _Pen(BasePen):
    def __init__(self, glyphs, scale, x0, y0):
        super().__init__(glyphs)
        self.ops, self.s, self.x0, self.y0 = [], scale, x0, y0

    def _p(self, p):
        return f"{self.x0 + p[0] * self.s:.3f} {self.y0 + p[1] * self.s:.3f}"

    def _moveTo(self, p):
        self.ops.append(f"{self._p(p)} m")

    def _lineTo(self, p):
        self.ops.append(f"{self._p(p)} l")

    def _curveToOne(self, a, b, c):
        self.ops.append(f"{self._p(a)} {self._p(b)} {self._p(c)} c")

    def _closePath(self):
        self.ops.append("h")


def _width(text, size_px, weight):
    glyphs, cmap, upm = _font(weight)
    return sum(glyphs[cmap.get(ord(c), ".notdef")].width for c in text) * size_px / upm


def _text(text, x_px, baseline_px, size_px, weight, gray=0.0):
    """Filled outlines; positions in template px from the top-left, converted to PDF pt."""
    glyphs, cmap, upm = _font(weight)
    scale = size_px * K / upm
    x, ops = x_px * K, []
    y = PAGE_H - baseline_px * K
    for ch in text:
        g = cmap.get(ord(ch), ".notdef")
        pen = _Pen(glyphs, scale, x, y)
        glyphs[g].draw(pen)
        ops += pen.ops
        x += glyphs[g].width * scale
    return f"{gray:.3f} g " + " ".join(ops) + " f" if ops else ""


def _fit(text, size_px, weight, max_px):
    """Shrink the font if one line would overflow."""
    w = _width(text, size_px, weight)
    return size_px if w <= max_px else size_px * max_px / w


def _wrap(text, size_px, weight, max_px, max_lines=2):
    words, lines = text.split(), []
    cur = ""
    for w in words:
        t = f"{cur} {w}".strip()
        if _width(t, size_px, weight) <= max_px or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:  # keep two lines; squeeze the rest into the last one
        lines = lines[:max_lines - 1] + [" ".join(lines[max_lines - 1:])]
    return lines


def _qr(data, x_px, y_top_px, size_px):
    qr = segno.make(data, error="m", micro=False)
    matrix = list(qr.matrix_iter(scale=1, border=0))
    n = len(matrix)
    cell = size_px * K / n
    x0, y0 = x_px * K, PAGE_H - y_top_px * K
    rects = [f"{x0 + c * cell:.3f} {y0 - (r + 1) * cell:.3f} {cell:.3f} {cell:.3f} re"
             for r, row in enumerate(matrix) for c, v in enumerate(row) if v]
    return "0 g " + " ".join(rects) + " f"


def label_ops(it, copy_no=1):
    """Drawing operators for one item label. `it` is a pulse.Item."""
    ops = []
    inner_l, inner_r = PAD_L, DESIGN_W - PAD_R
    width = inner_r - inner_l

    # line 1: order number (57px, 900) + " | From | Code" (45px, 700, #444)
    y = PAD_T
    order = it.order_number or ""
    tag = f" | {FROM_NAMES.get(it.source, it.source)} | {it.print_code or '-'}"
    s1 = _fit(order, 57, "black", width * 0.45)
    s2 = _fit(tag, 45, "bold", width - _width(order, s1, "black"))
    base = y + s1 * 0.95
    ops.append(_text(order, inner_l, base, s1, "black"))
    ops.append(_text(tag, inner_l + _width(order, s1, "black"), base, s2, "bold", gray=0x44 / 255))
    y += s1 * 1.2 + 9

    # line 2: description, upper case, 54px 900, line-height 1.1, wraps to 2 lines
    lines = _wrap((it.description or "").upper(), 54, "black", width)
    size = min(_fit(ln, 54, "black", width) for ln in lines) if lines else 54
    for ln in lines:
        ops.append(_text(ln, inner_l, y + size * 0.92, size, "black"))
        y += size * 1.1
    y += 6

    # divider (3px) across the full width
    ops.append(f"0 G {3 * K:.3f} w {inner_l * K:.3f} {PAGE_H - (y + 1.5) * K:.3f} m "
               f"{inner_r * K:.3f} {PAGE_H - (y + 1.5) * K:.3f} l S")
    y += 3 + 6

    left_w = width - RIGHT_COL
    # item (51px, 700, #222, upper) / customer name (48px, 900) / QTY
    item = (it.item_type or "").upper()
    s = _fit(item, 51, "bold", left_w)
    ops.append(_text(item, inner_l, y + s * 0.95, s, "bold", gray=0x22 / 255))
    yl = y + s * 1.2 + 9
    name = it.customer_name or ""
    s = _fit(name, 48, "black", left_w)
    ops.append(_text(name, inner_l, yl + s * 0.95, s, "black"))
    yl += s * 1.2
    qty_base = yl + 69 * 0.95
    ops.append(_text("QTY", inner_l, qty_base, 27, "bold", gray=0x55 / 255))
    q = max(1, int(it.quantity or 1))
    ops.append(_text(f"{min(copy_no, q)} / {q}", inner_l + _width("QTY", 27, "bold") + 14, qty_base, 69, "black"))

    # right column: QR of the component barcode, item barcode text under it
    qr_x = inner_r - QR_PX
    ops.append(_qr(it.component_barcode, qr_x, y, QR_PX))
    bc = it.item_barcode or it.component_barcode
    s = _fit(bc, 20, "black", RIGHT_COL)
    ops.append(_text(bc, qr_x + QR_PX / 2 - _width(bc, s, "black") / 2, y + QR_PX + 3 + s, s, "black"))
    return "\n".join(o for o in ops if o)


def build_labels(items, out_path, title):
    """One label per piece (page), in the order given (= slot order on the sheet)."""
    pdf = pikepdf.new()
    pdf.docinfo[Name.Title] = title
    pdf.docinfo[Name.Creator] = "MT3 Manual Batching"
    box = Array([0, 0, PAGE_W, PAGE_H])
    for it in items:
        pdf.pages.append(pikepdf.Page(Dictionary(
            Type=Name.Page, MediaBox=box, CropBox=box, TrimBox=box,
            Contents=pdf.make_stream(label_ops(it).encode("latin-1")), Resources=Dictionary())))
    pdf.save(out_path, min_version="1.6")


def custom_label_ops(e):
    """Basic 2x1 label for custom artwork (no Pulse order), same look as the item label:
         SUB_CUSTOM_..._01 | Custom artwork
         <TEXT PRINTED BESIDE THE ARTWORK>
         ------------------------------------------------
         SHEET S1-3                               [QR: run|S1-3|text]
         QTY 2 / 4                                 S1-3
    e: {run_id, pos, name, copy_no, copies}"""
    ops = []
    inner_l, inner_r = PAD_L, DESIGN_W - PAD_R
    width = inner_r - inner_l
    y = PAD_T
    head, tag = e["run_id"], " | Custom artwork"
    s1 = _fit(head, 45, "black", width * 0.62)
    base = y + s1 * 0.95
    ops.append(_text(head, inner_l, base, s1, "black"))
    ops.append(_text(tag, inner_l + _width(head, s1, "black"), base, _fit(tag, 40, "bold", width - _width(head, s1, "black")),
                     "bold", gray=0x44 / 255))
    y += s1 * 1.2 + 9
    lines = _wrap((e["name"] or "Custom artwork").upper(), 54, "black", width)
    size = min(_fit(ln, 54, "black", width) for ln in lines) if lines else 54
    for ln in lines:
        ops.append(_text(ln, inner_l, y + size * 0.92, size, "black"))
        y += size * 1.1
    y += 6
    ops.append(f"0 G {3 * K:.3f} w {inner_l * K:.3f} {PAGE_H - (y + 1.5) * K:.3f} m "
               f"{inner_r * K:.3f} {PAGE_H - (y + 1.5) * K:.3f} l S")
    y += 3 + 6
    sheet = f"SHEET {e['pos']}"
    ops.append(_text(sheet, inner_l, y + 51 * 0.95, 51, "bold", gray=0x22 / 255))
    yl = y + 51 * 1.2 + 9
    qty_base = yl + 69 * 0.95
    ops.append(_text("QTY", inner_l, qty_base, 27, "bold", gray=0x55 / 255))
    ops.append(_text(f"{e['copy_no']} / {e['copies']}", inner_l + _width("QTY", 27, "bold") + 14, qty_base, 69, "black"))
    qr_x = inner_r - QR_PX
    ops.append(_qr(f"{e['run_id']}|{e['pos']}|{e['name']}", qr_x, y, QR_PX))
    ops.append(_text(e["pos"], qr_x + QR_PX / 2 - _width(e["pos"], 20, "black") / 2, y + QR_PX + 3 + 20, 20, "black"))
    return "\n".join(o for o in ops if o)


def build_custom_labels(entries, out_path, title):
    """One basic label per custom piece (page), in slot order."""
    pdf = pikepdf.new()
    pdf.docinfo[Name.Title] = title
    pdf.docinfo[Name.Creator] = "MT3 Manual Batching"
    box = Array([0, 0, PAGE_W, PAGE_H])
    for e in entries:
        pdf.pages.append(pikepdf.Page(Dictionary(
            Type=Name.Page, MediaBox=box, CropBox=box, TrimBox=box,
            Contents=pdf.make_stream(custom_label_ops(e).encode("latin-1", "replace")), Resources=Dictionary())))
    pdf.save(out_path, min_version="1.6")
