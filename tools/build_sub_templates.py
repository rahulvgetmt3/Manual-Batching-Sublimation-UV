#!/usr/bin/env python3
"""Rebuild the built-in Sublimation templates (6UP, 6UP-EXT) from the team's .ai files.

Uses app/sub_templates.process(), which also handles templates uploaded in the portal.
Writes app/templates/sublimation/<KEY>.pdf + <KEY>.json, and swop.icc ('U.S. Web Coated
(SWOP) v2', taken from the template; used only to convert colours, never embedded).

    .venv/bin/python tools/build_sub_templates.py
"""

import sys
from pathlib import Path

import pikepdf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.sub_templates import BUILTIN_DIR, MM, process  # noqa: E402

SRC = ROOT / "Reference" / "Sublimation" / "Sublimation Templates"
BUILTIN = {
    "6UP": ("Sublimation 6UP - Dieline (Without Artwork).ai", "Sublimation 6UP"),
    "6UP-EXT": ("Sublimation 6UP Extended - Dieline (Without Artwork).ai", "Sublimation 6UP Extended"),
}
# Name baselines measured in the team's filled reference (12.3 mm / 310.3 mm from the left edge)
NAME_X = {"L": round(12.3 * MM, 2), "R": round(310.3 * MM, 2)}


def main():
    for key, (fname, title) in BUILTIN.items():
        meta = process(SRC / fname, key, title, BUILTIN_DIR, name_x=NAME_X)
        print(f"{key}: page {meta['page'][0] / MM:.1f} x {meta['page'][1] / MM:.1f} mm, "
              f"{len(meta['slots'])} slots, removed {meta['removed']}")
        src = pikepdf.open(SRC / fname)
        res = src.pages[0].Resources
        for _, cs in (res.ColorSpace.items() if "/ColorSpace" in res else []):
            if isinstance(cs, pikepdf.Array) and str(cs[0]) == "/ICCBased" and int(cs[1].N) == 4:
                (BUILTIN_DIR / "swop.icc").write_bytes(cs[1].read_bytes())
    old = BUILTIN_DIR / "templates.json"
    if old.exists():
        old.unlink()
    assert (BUILTIN_DIR / "swop.icc").exists(), "SWOP profile not found in templates"


if __name__ == "__main__":
    main()
