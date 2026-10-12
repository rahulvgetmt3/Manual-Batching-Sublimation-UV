"""Sublimation sheet templates: any size (1UP, 6UP, 10UP, ...).

A template is the team's dieline exported as PDF / PDF-compatible .ai with the slot frames
drawn as rectangles. Processing it:
  - finds the slots: the most common repeated rectangle size (stroked frames), ordered
    top row first, left to right;
  - removes what must not print: the slot frames, QR codes (13-17 mm corner squares) and
    hidden sample codes ("MT3-A10..."); colour bars, registration marks and TL/BR stay;
  - works out where each piece's name goes: in the margin beside the slot, on the left
    for the left half of the columns and on the right for the right half (the built-in
    6UP templates use the exact positions from the team's reference);
  - records the registration-mark bands near the edges (informational).

Built-in templates live in app/templates/sublimation/ (6UP, 6UP-EXT); uploaded ones in
data/templates/sublimation/ (TEMPLATES_DIR). Each folder holds <KEY>.pdf + <KEY>.json.
"""

import json
import os
import re
from pathlib import Path

import pikepdf

MM = 72 / 25.4
BUILTIN_DIR = Path(__file__).resolve().parent / "templates" / "sublimation"
USER_DIR = Path(os.environ.get("TEMPLATES_DIR",
                               Path(__file__).resolve().parent.parent / "data" / "templates" / "sublimation"))
NAME_SIZE = 15.08                 # pt; keep in step with sub_build
CAP = 0.72 * NAME_SIZE            # approx. cap height: how far rotated text reaches left of its baseline
PAINT = {"S", "s", "f", "F", "f*", "B", "B*", "b", "b*"}
STROKE = {"S", "s", "B", "B*", "b", "b*"}
PATH = {"m", "l", "c", "v", "y", "re", "h"}
DEFAULT_TEMPLATE = "6UP-EXT"


class TemplateError(Exception):
    pass


def safe_key(name):
    key = re.sub(r"[^A-Z0-9]+", "-", (name or "").upper()).strip("-")
    if not key or len(key) > 24:
        raise TemplateError("Template name: 1-24 letters/numbers, e.g. 10UP or 1UP-PIXEL")
    return key


def _mul(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return [a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D, e * A + f * C + E, e * B + f * D + F]


def _pt(m, x, y):
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def _is_rect(pts):
    """Axis-aligned rectangle from a subpath's points (4-5 corners)."""
    if not 4 <= len(pts) <= 5:
        return None
    xs = sorted({round(p[0], 1) for p in pts})
    ys = sorted({round(p[1], 1) for p in pts})
    if len(xs) != 2 or len(ys) != 2:
        return None
    return [xs[0], ys[0], xs[1] - xs[0], ys[1] - ys[0]]


def _scan(page):
    """Walk the content: every painted path object with its op range, bbox and rectangles."""
    ops = list(pikepdf.parse_content_stream(page))
    objs, texts = [], []
    ctm, stack = [1, 0, 0, 1, 0, 0], []
    pts, start, rects, sub, curve = [], None, [], [], False
    bt = None
    for i, (operands, op) in enumerate(ops):
        o = str(op)
        if o == "q":
            stack.append(ctm)
        elif o == "Q":
            ctm = stack.pop() if stack else ctm
        elif o == "cm":
            ctm = _mul([float(x) for x in operands], ctm)
        elif o in PATH:
            start = i if start is None else start
            v = [float(x) for x in operands]
            if o == "re":
                x, y, w, h = v
                corners = [_pt(ctm, x, y), _pt(ctm, x + w, y), _pt(ctm, x + w, y + h), _pt(ctm, x, y + h)]
                pts += corners
                r = _is_rect(corners)
                if r:
                    rects.append(r)
            elif o == "m":
                if sub and not curve and _is_rect(sub):
                    rects.append(_is_rect(sub))
                sub, curve = [_pt(ctm, v[0], v[1])], False
                pts += sub
            elif o == "l":
                p = _pt(ctm, v[0], v[1])
                sub.append(p)
                pts.append(p)
            elif o in ("c", "v", "y"):
                curve = True
                pts += [_pt(ctm, v[k], v[k + 1]) for k in range(0, len(v), 2)]
        elif o in PAINT or o == "n":
            if sub and not curve and _is_rect(sub):
                rects.append(_is_rect(sub))
            if pts and o != "n":
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                objs.append({"start": start, "end": i, "op": o, "stroke": o in STROKE,
                             "bbox": [min(xs), min(ys), max(xs), max(ys)], "rects": rects})
            pts, start, rects, sub, curve = [], None, [], [], False
        elif o == "BT":
            bt = i
        elif o == "ET" and bt is not None:
            text = "".join(bytes(x[0][0]).decode("latin1") for x in ops[bt:i + 1]
                           if str(x[1]) == "Tj" and x[0] and isinstance(x[0][0], pikepdf.String))
            texts.append({"start": bt, "end": i, "text": text})
            bt = None
    return ops, objs, texts


def _find_slots(objs, page_w, page_h):
    """Slots = the most common stroked rectangle size (at least 20 x 20 mm, smaller than the page)."""
    cands = []
    for ob in objs:
        if not ob["stroke"]:
            continue
        for r in ob["rects"]:
            x, y, w, h = r
            if w >= 20 * MM and h >= 20 * MM and w < page_w * 0.95 and h < page_h * 0.95:
                cands.append((r, ob))
    if not cands:
        return [], []
    groups = {}
    for r, ob in cands:
        groups.setdefault((round(r[2] / MM), round(r[3] / MM)), []).append((r, ob))
    best = max(groups.values(), key=lambda g: (len(g), g[0][0][2] * g[0][0][3]))
    slots, owners = [], []
    for r, ob in best:
        if not any(abs(r[0] - s[0]) < 2 and abs(r[1] - s[1]) < 2 for s in slots):
            slots.append(r)
            owners.append(ob)
    # rows top to bottom (tolerance 5 mm), then left to right
    slots.sort(key=lambda s: (-round((s[1] + s[3]) / (5 * MM)), s[0]))
    return slots, owners


def _name_positions(slots, page_w):
    """Baseline x for each slot's name: in the margin beside it (left half -> left side)."""
    lefts = sorted({round(s[0], 0) for s in slots})
    cols = []
    for x in lefts:
        if not cols or x - cols[-1] > 5 * MM:
            cols.append(x)
    out = []
    for s in slots:
        c = min(range(len(cols)), key=lambda k: abs(cols[k] - s[0]))
        left_side = c < len(cols) / 2 or len(cols) == 1
        if left_side:
            prev = [o[0] + o[2] for o in slots if o[0] + o[2] <= s[0] + 1 and abs(o[1] - s[1]) < s[3]]
            bound = max(prev) if prev else 0
            centre = (bound + s[0]) / 2
            out.append({"side": "L", "x": round(centre + CAP / 2, 2)})
        else:
            nxt = [o[0] for o in slots if o[0] >= s[0] + s[2] - 1 and abs(o[1] - s[1]) < s[3]]
            bound = min(nxt) if nxt else page_w
            centre = (s[0] + s[2] + bound) / 2
            out.append({"side": "R", "x": round(centre + CAP / 2, 2)})
    return out


def process(src_path, key, title, out_dir, name_x=None):
    """Clean a template and write <key>.pdf + <key>.json into out_dir. Returns the metadata."""
    try:
        src = pikepdf.open(src_path)
    except Exception:  # noqa: BLE001 - shown to the user
        raise TemplateError("Not a PDF or PDF-compatible .ai file. In Illustrator use Save As .ai with "
                            "'Create PDF Compatible File' ticked, or Save a Copy as PDF.")
    if len(src.pages) < 1:
        raise TemplateError("The file has no pages")
    page = src.pages[0]
    box = [float(v) for v in page.MediaBox]
    page_w, page_h = box[2] - box[0], box[3] - box[1]
    ops, objs, texts = _scan(page)
    slots, owners = _find_slots(objs, page_w, page_h)
    if not slots:
        raise TemplateError("No slot frames found. The dieline needs one stroked rectangle per piece "
                            "(like the green frames in the 6UP template).")
    drop = set()
    for ob in owners:                                     # slot frames: position kept, not printed
        drop.update(range(ob["start"], ob["end"] + 1))
    marks, qr = [], 0
    for ob in objs:
        x0, y0, x1, y1 = ob["bbox"]
        w, h = (x1 - x0) / MM, (y1 - y0) / MM
        if 13 <= w <= 17 and 13 <= h <= 17:               # QR code / QR placeholder
            drop.update(range(ob["start"], ob["end"] + 1))
            qr += 1
        elif 5 <= w <= 9 and 5 <= h <= 9 and (x1 < 25 * MM or x0 > page_w - 25 * MM):
            marks.append(["L" if x1 < 25 * MM else "R", round(y0, 2), round(y1, 2)])
    for t in texts:                                       # hidden sample codes
        if "MT3-A" in t["text"]:
            drop.update(range(t["start"], t["end"] + 1))

    kept = [op for i, op in enumerate(ops) if i not in drop]
    page.Contents = src.make_stream(pikepdf.unparse_content_stream(kept))
    for k in ("/PieceInfo", "/Thumb"):
        if k in page.obj:
            del page.obj[k]
    out = pikepdf.new()
    out.pages.append(page)
    if "/OCProperties" in src.Root:
        out.Root.OCProperties = out.copy_foreign(src.make_indirect(src.Root.OCProperties))
    out_dir.mkdir(parents=True, exist_ok=True)
    out.save(out_dir / f"{key}.pdf")

    names = _name_positions(slots, page_w)
    if name_x:                                            # fixed positions (built-in 6UP, from reference)
        for n in names:
            n["x"] = name_x[n["side"]]
    meta = {
        "key": key, "title": title,
        "page": [round(page_w, 3), round(page_h, 3)],
        "slots": [[round(v, 3) for v in s] for s in slots],
        "names": names,
        "marks": marks,
        "removed": {"frames": len(owners), "qr": qr},
    }
    (out_dir / f"{key}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def registry():
    """All templates, built-in first, then uploaded. key -> metadata (+ 'pdf', 'builtin')."""
    out = {}
    for d, builtin in ((BUILTIN_DIR, True), (USER_DIR, False)):
        if not d.exists():
            continue
        for j in sorted(d.glob("*.json")):
            if j.name == "templates.json":
                continue
            try:
                meta = json.loads(j.read_text(encoding="utf-8"))
            except ValueError:
                continue
            pdf = d / f"{j.stem}.pdf"
            if pdf.exists() and j.stem not in out:
                meta.update(pdf=str(pdf), builtin=builtin)
                out[j.stem] = meta
    return out


def summary(meta):
    """What the UI shows for a template."""
    s0 = meta["slots"][0]
    return {
        "key": meta["key"], "title": meta["title"], "builtin": meta.get("builtin", False),
        "slots": len(meta["slots"]),
        "page_mm": [round(v / MM, 1) for v in meta["page"]],
        "slot_mm": [round(s0[2] / MM, 1), round(s0[3] / MM, 1)],
        "layout": {"page": meta["page"], "slots": meta["slots"], "names": meta.get("names", [])},
        "removed": meta.get("removed", {}),
    }


def delete(key):
    meta = registry().get(key)
    if not meta:
        raise TemplateError(f"Template {key} not found")
    if meta.get("builtin"):
        raise TemplateError("Built-in templates cannot be deleted")
    for ext in ("pdf", "json"):
        (USER_DIR / f"{key}.{ext}").unlink(missing_ok=True)
