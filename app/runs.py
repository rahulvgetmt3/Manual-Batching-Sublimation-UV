"""Turn a list of scanned component barcodes into a finished run folder + ZIP."""

import datetime as dt
import json
import os
import re
import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .fetch import cached_file, image_info
from .layout import layout
from .manifest import write_manifest
from .pdf_build import build_pdfs
from .spot_pdf import build_spot_pdf
from .pulse import lookup_many, normalise

RUNS_DIR = Path(os.environ.get("RUNS_DIR", Path(__file__).resolve().parent.parent / "data" / "runs"))


def _safe(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-")


def _claim_run_dir(line):
    """Create the next free UV_<line>_<date>_NN folder; mkdir is atomic, so parallel runs never collide."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d")
    n = 1 + sum(1 for p in RUNS_DIR.glob(f"UV_{line}_{stamp}_*") if p.is_dir())
    while True:
        run_id = f"UV_{line}_{stamp}_{n:02d}"
        try:
            (RUNS_DIR / run_id).mkdir()
            return run_id
        except FileExistsError:
            n += 1


def create_run(barcodes, user=""):
    barcodes = normalise(barcodes)
    if not barcodes:
        raise ValueError("No barcodes scanned")
    found, errors = lookup_many(barcodes)
    if errors:
        raise ValueError("; ".join(errors.values()))
    items = [found[b] for b in barcodes]
    lines = {it.line for it in items}
    if len(lines) > 1:
        raise ValueError("LUX and Mirror print with different methods and cannot share a PDF; generate them separately")
    line = lines.pop()

    def _get(it):
        try:
            return cached_file(it.fetch_url)
        except Exception as e:  # noqa: BLE001 - reported per barcode
            raise ValueError(f"{it.component_barcode}: could not download print file ({e})") from e

    with ThreadPoolExecutor(8) as ex:
        paths = list(ex.map(_get, items))
    pieces = []
    for it, path in zip(items, paths):
        info = image_info(path)
        pieces.append({"label": it.label, "w": info["w_pt"], "h": info["h_pt"], "path": path, "info": info})

    placements = layout(pieces)

    run_id = _claim_run_dir(line)
    out = RUNS_DIR / run_id
    (out / "files").mkdir()
    file_pdf = out / f"{run_id}_FILE.pdf"
    die_pdf = out / f"{run_id}_DIE.pdf"
    xlsx = out / f"{run_id}_manifest.xlsx"
    build_pdfs(placements, pieces, file_pdf, die_pdf, run_id)
    sheets_n = max(p.sheet for p in placements)
    spot_pdfs = []
    for s in range(1, sheets_n + 1):
        sp = out / (f"{run_id}_SPOT.pdf" if sheets_n == 1 else f"{run_id}_SPOT_S{s}.pdf")
        build_spot_pdf([p for p in placements if p.sheet == s], pieces, items, sp, sp.stem)
        spot_pdfs.append(sp)
    write_manifest(placements, items, xlsx, run_id)

    for p in placements:
        it, src = items[p.index], pieces[p.index]["path"]
        name = f"S{p.sheet}-{p.position:03d}_{it.batch_number}_{_safe(it.print_code)}_{it.component_barcode}{src.suffix}"
        shutil.copyfile(src, out / "files" / name)

    sheets = max(p.sheet for p in placements)
    meta = {
        "run_id": run_id,
        "line": line,
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "user": user,
        "pieces": len(items),
        "sheets": sheets,
        "barcodes": barcodes,
    }
    (out / "run.json").write_text(json.dumps(meta, indent=2))

    zip_path = out / f"{run_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in (file_pdf, die_pdf, *spot_pdfs, xlsx):
            z.write(f, f.name)
        for f in sorted((out / "files").iterdir()):
            z.write(f, f"files/{f.name}")
    return meta


def list_runs(limit=100):
    if not RUNS_DIR.exists():
        return []
    metas = []
    for d in RUNS_DIR.iterdir():
        m = d / "run.json"
        if m.exists():
            metas.append(json.loads(m.read_text()))
    return sorted(metas, key=lambda m: m["created"], reverse=True)[:limit]


def run_file(run_id, kind):
    if not re.fullmatch(r"UV_[A-Z]+_\d{8}_\d+", run_id):
        return None
    out = RUNS_DIR / run_id
    if kind == "spot":
        return _spot_download(out, run_id)
    name = {"zip": f"{run_id}.zip", "file": f"{run_id}_FILE.pdf",
            "die": f"{run_id}_DIE.pdf", "xlsx": f"{run_id}_manifest.xlsx"}.get(kind)
    p = out / name if name else None
    return p if p and p.exists() else None


def _spot_download(out, run_id):
    """The spot PDF; for a multi-sheet run, one ZIP holding every sheet's spot PDF."""
    psds = sorted(out.glob(f"{run_id}_SPOT*.pdf"))
    if len(psds) <= 1:
        return psds[0] if psds else None
    z = out / f"{run_id}_SPOT.zip"
    if not z.exists():
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in psds:
                zf.write(f, f.name)
    return z
