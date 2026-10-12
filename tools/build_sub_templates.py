#!/usr/bin/env python3
"""Build the clean Sublimation sheet templates the app uses.

Reads the team's Illustrator templates (PDF-compatible .ai) from
Reference/Sublimation/Sublimation Templates/ and writes to app/templates/sublimation/:

  6UP.pdf, 6UP-EXT.pdf  one-page backgrounds: colour bars, registration marks, TL/BR.
                        Removed: the green slot frames (positions are kept in templates.json),
                        the QR codes (15 mm corner squares) and the hidden sample codes
                        ("MT3-A10..").
  templates.json        page size, the 6 slot frames (pt, PDF origin bottom-left) ordered
                        TL, TR, ML, MR, BL, BR, and the registration-mark y-bands per edge,
                        so the side names can avoid them.
  swop.icc              'U.S. Web Coated (SWOP) v2', the CMYK profile the team's
                        templates and artwork use. It is used only to convert colours
                        and is never embedded in the output.

Re-run this whenever the team updates a template:
    .venv/bin/python tools/build_sub_templates.py
"""

import json
from pathlib import Path

import pikepdf

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "Reference" / "Sublimation" / "Sublimation Templates"
OUT = ROOT / "app" / "templates" / "sublimation"
TEMPLATES = {
    "6UP": ("Sublimation 6UP - Dieline (Without Artwork).ai", "Sublimation 6UP"),
    "6UP-EXT": ("Sublimation 6UP Extended - Dieline (Without Artwork).ai", "Sublimation 6UP Extended"),
}
MM = 72 / 25.4
PAINT = {"S", "s", "f", "F", "f*", "B", "B*", "b", "b*"}
PATH = {"m", "l", "c", "v", "y", "re", "h"}


def _mul(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return [a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D, e * A + f * C + E, e * B + f * D + F]


def _pt(m, x, y):
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def clean(page):
    """Return (kept ops, slot frames) for a template page."""
    ops = list(pikepdf.parse_content_stream(page))
    drop = set()
    slots = []
    marks = []  # registration-mark shapes (about 6-8 mm) near the left/right edges
    ctm, stack, pts, start = [1, 0, 0, 1, 0, 0], [], [], None
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
                pts += [_pt(ctm, x, y), _pt(ctm, x + w, y + h)]
            else:
                pts += [_pt(ctm, v[k], v[k + 1]) for k in range(0, len(v), 2)]
        elif o in PAINT or o == "n":
            if pts and o != "n":
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                w, h = (max(xs) - min(xs)) / MM, (max(ys) - min(ys)) / MM
                if 13 <= w <= 17 and 13 <= h <= 17:          # QR code / QR placeholder
                    drop.update(range(start, i + 1))
                elif 5 <= w <= 9 and 5 <= h <= 9 and (max(xs) < 25 * MM or min(xs) > 293 * MM):
                    marks.append(["L" if max(xs) < 25 * MM else "R", min(ys), max(ys)])
                elif o in ("S", "s") and 120 <= w <= 140 and 180 <= h <= 230:  # green slot frame
                    slots.append([min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)])
                    drop.update(range(start, i + 1))   # position kept, frame not printed (Rahul)
            pts, start = [], None
        elif o == "BT":
            bt = i
        elif o == "ET" and bt is not None:
            text = "".join(bytes(x[0][0]).decode("latin1") for x in ops[bt:i + 1]
                           if str(x[1]) == "Tj" and isinstance(x[0][0], pikepdf.String))
            if "MT3-A" in text:                               # hidden sample codes
                drop.update(range(bt, i + 1))
            bt = None
    kept = [op for i, op in enumerate(ops) if i not in drop]
    # unique slots, ordered top row first, then left before right
    uniq = []
    for s in slots:
        if not any(abs(s[0] - u[0]) < 1 and abs(s[1] - u[1]) < 1 for u in uniq):
            uniq.append(s)
    uniq.sort(key=lambda s: (-round(s[1]), s[0]))
    # merge mark shapes into one y-band per mark and side
    bands = []
    for side, y0, y1 in sorted(marks):
        if bands and bands[-1][0] == side and y0 <= bands[-1][2] + 1:
            bands[-1][2] = max(bands[-1][2], y1)
        else:
            bands.append([side, y0, y1])
    return kept, uniq, len(drop), bands


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {}
    for key, (fname, title) in TEMPLATES.items():
        src = pikepdf.open(SRC / fname)
        page = src.pages[0]
        kept, slots, ndrop, bands = clean(page)
        assert len(slots) == 6, f"{key}: expected 6 slot frames, found {len(slots)}"
        page.Contents = src.make_stream(pikepdf.unparse_content_stream(kept))
        for k in ("/PieceInfo", "/Thumb"):
            if k in page.obj:
                del page.obj[k]
        out = pikepdf.new()
        out.pages.append(page)
        if "/OCProperties" in src.Root:
            out.Root.OCProperties = out.copy_foreign(src.make_indirect(src.Root.OCProperties))
        out.save(OUT / f"{key}.pdf")
        box = [float(v) for v in page.MediaBox]
        meta[key] = {"title": title, "page": [box[2], box[3]], "slots": [[round(v, 3) for v in s] for s in slots],
                     "marks": [[b[0], round(b[1], 2), round(b[2], 2)] for b in bands]}
        print(f"{key}: page {box[2] / MM:.1f} x {box[3] / MM:.1f} mm, 6 slots, removed {ndrop} ops")

        if "/ColorSpace" in page.Resources:
            for _, cs in page.Resources.ColorSpace.items():
                if isinstance(cs, pikepdf.Array) and str(cs[0]) == "/ICCBased" and int(cs[1].N) == 4:
                    (OUT / "swop.icc").write_bytes(cs[1].read_bytes())
    (OUT / "templates.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    assert (OUT / "swop.icc").exists(), "SWOP profile not found in templates"


if __name__ == "__main__":
    main()
