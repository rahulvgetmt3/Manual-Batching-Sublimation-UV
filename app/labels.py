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
from fontTools.ttLib import TTFont
from pikepdf import Array, Dictionary, Name

from .pdf_build import _PdfPathPen

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
        pen = _PdfPathPen(scale, x, y, glyphs)
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


def _header(ops, head, tag, head_px, tag_px, head_share):
    """Line 1: bold head (order number / run id) + grey ' | …' tag. Returns the next y."""
    width = DESIGN_W - PAD_R - PAD_L
    s1 = _fit(head, head_px, "black", width * head_share)
    s2 = _fit(tag, tag_px, "bold", width - _width(head, s1, "black"))
    base = PAD_T + s1 * 0.95
    ops.append(_text(head, PAD_L, base, s1, "black"))
    ops.append(_text(tag, PAD_L + _width(head, s1, "black"), base, s2, "bold", gray=0x44 / 255))
    return PAD_T + s1 * 1.2 + 9


def _description(ops, text, y):
    """Line 2: upper case, 54px 900, line-height 1.1, wraps to 2 lines; then the 3px divider."""
    inner_r, width = DESIGN_W - PAD_R, DESIGN_W - PAD_R - PAD_L
    lines = _wrap(text.upper(), 54, "black", width)
    size = min(_fit(ln, 54, "black", width) for ln in lines) if lines else 54
    for ln in lines:
        ops.append(_text(ln, PAD_L, y + size * 0.92, size, "black"))
        y += size * 1.1
    y += 6
    ops.append(f"0 G {3 * K:.3f} w {PAD_L * K:.3f} {PAGE_H - (y + 1.5) * K:.3f} m "
               f"{inner_r * K:.3f} {PAGE_H - (y + 1.5) * K:.3f} l S")
    return y + 3 + 6


def _qty_and_qr(ops, qty_top, qty_text, y, qr_data, caption, caption_px):
    """QTY n / m on the left at qty_top; QR in the right column at y with its caption underneath."""
    qty_base = qty_top + 69 * 0.95
    ops.append(_text("QTY", PAD_L, qty_base, 27, "bold", gray=0x55 / 255))
    ops.append(_text(qty_text, PAD_L + _width("QTY", 27, "bold") + 14, qty_base, 69, "black"))
    qr_x = DESIGN_W - PAD_R - QR_PX
    ops.append(_qr(qr_data, qr_x, y, QR_PX))
    ops.append(_text(caption, qr_x + QR_PX / 2 - _width(caption, caption_px, "black") / 2,
                     y + QR_PX + 3 + caption_px, caption_px, "black"))


def label_ops(it):
    """Drawing operators for one item label. `it` is a pulse.Item."""
    ops = []
    left_w = DESIGN_W - PAD_R - PAD_L - RIGHT_COL
    order = it.order_number or ""
    y = _header(ops, order, f" | {FROM_NAMES.get(it.source, it.source)} | {it.print_code or '-'}", 57, 45, 0.45)
    y = _description(ops, it.description or "", y)
    # item (51px, 700, #222, upper) / customer name (48px, 900) / QTY
    item = (it.item_type or "").upper()
    s = _fit(item, 51, "bold", left_w)
    ops.append(_text(item, PAD_L, y + s * 0.95, s, "bold", gray=0x22 / 255))
    yl = y + s * 1.2 + 9
    name = it.customer_name or ""
    s = _fit(name, 48, "black", left_w)
    ops.append(_text(name, PAD_L, yl + s * 0.95, s, "black"))
    yl += s * 1.2
    q = max(1, int(it.quantity or 1))
    # right column: QR of the component barcode, item barcode text under it
    bc = it.item_barcode or it.component_barcode
    _qty_and_qr(ops, yl, f"1 / {q}", y, it.component_barcode, bc, _fit(bc, 20, "black", RIGHT_COL))
    return "\n".join(o for o in ops if o)


def custom_label_ops(e):
    """Basic 2x1 label for custom artwork (no Pulse order), same look as the item label:
         SUB_CUSTOM_..._01 | Custom artwork
         <TEXT PRINTED BESIDE THE ARTWORK>
         ------------------------------------------------
         SHEET S1-3                               [QR: run|S1-3|text]
         QTY 2 / 4                                 S1-3
    e: {run_id, pos, name, copy_no, copies}"""
    ops = []
    y = _header(ops, e["run_id"], " | Custom artwork", 45, 40, 0.62)
    y = _description(ops, e["name"] or "Custom artwork", y)
    ops.append(_text(f"SHEET {e['pos']}", PAD_L, y + 51 * 0.95, 51, "bold", gray=0x22 / 255))
    _qty_and_qr(ops, y + 51 * 1.2 + 9, f"{e['copy_no']} / {e['copies']}", y,
                f"{e['run_id']}|{e['pos']}|{e['name']}", e["pos"], 20)
    return "\n".join(o for o in ops if o)


def build_labels(entries, out_path, title, ops_fn=label_ops):
    """One 2x1 label per piece (page), in the order given (= slot order on the sheet).
    ops_fn: label_ops for Pulse items, custom_label_ops for custom artwork entries."""
    pdf = pikepdf.new()
    pdf.docinfo[Name.Title] = title
    pdf.docinfo[Name.Creator] = "MT3 Manual Batching"
    box = Array([0, 0, PAGE_W, PAGE_H])
    for e in entries:
        pdf.pages.append(pikepdf.Page(Dictionary(
            Type=Name.Page, MediaBox=box, CropBox=box, TrimBox=box,
            Contents=pdf.make_stream(ops_fn(e).encode("latin-1", "replace")), Resources=Dictionary())))
    pdf.save(out_path, min_version="1.6")
