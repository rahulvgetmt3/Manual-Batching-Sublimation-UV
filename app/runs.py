"""Turn a list of scanned component barcodes into a finished run folder + ZIP."""

import datetime as dt
import json
import os
import re
import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .fetch import cached_file, cached_path, image_info
from .layout import Placement, layout
from .manifest import write_manifest
from .pdf_build import build_pdfs
from .spot_pdf import build_spot_pdf
from .pulse import lookup_many, normalise
from .labels import build_custom_labels, build_labels
from .sub_build import build_sheet, image_mode
from .sub_templates import DEFAULT_TEMPLATE, registry

RUNS_DIR = Path(os.environ.get("RUNS_DIR", Path(__file__).resolve().parent.parent / "data" / "runs"))


def _safe(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-")


RUN_ID_RE = re.compile(r"(UV_[A-Z]+|SUB_(BOLD|CLASSIC|ESSENTIAL|OTHER|CUSTOM)_[A-Z0-9-]{1,24}_(RGB|CMYK))_\d{8}_\d+")


def _claim_run_dir(line, prefix="UV"):
    """Create the next free <prefix>_<line>_<date>_NN folder; mkdir is atomic, so parallel runs never collide."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d")
    n = 1 + sum(1 for p in RUNS_DIR.glob(f"{prefix}_{line}_{stamp}_*") if p.is_dir())
    while True:
        run_id = f"{prefix}_{line}_{stamp}_{n:02d}"
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
        "process": "uv",
        "line": line,
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "user": user,
        "pieces": len(items),
        "sheets": sheets,
        "barcodes": barcodes,
    }
    (out / "run.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    zip_path = out / f"{run_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in (file_pdf, die_pdf, *spot_pdfs, xlsx):
            z.write(f, f.name)
        for f in sorted((out / "files").iterdir()):
            z.write(f, f"files/{f.name}")
    return meta


def _download_all(items):
    def _get(it):
        try:
            return cached_file(it.fetch_url)
        except Exception as e:  # noqa: BLE001 - reported per barcode
            raise ValueError(f"{it.component_barcode}: could not download print file ({e})") from e

    with ThreadPoolExecutor(8) as ex:
        return list(ex.map(_get, items))


def create_sub_run(barcodes, template=DEFAULT_TEMPLATE, color="CMYK", user="", mirror=True):
    """Sublimation: one PDF per 6-up sheet in the chosen template, artwork mirrored and centred,
    names beside each piece, artwork exported as RGB or CMYK."""
    template = template or DEFAULT_TEMPLATE  # default: 6UP Extended (Rahul)
    templates = registry()
    if template not in templates:
        raise ValueError(f"Unknown template {template!r}")
    per_sheet = len(templates[template]["slots"])
    color = (color or "CMYK").upper()      # default: CMYK (Rahul)
    if color not in ("RGB", "CMYK"):
        raise ValueError("Colour must be RGB or CMYK")
    barcodes = normalise(barcodes)
    if not barcodes:
        raise ValueError("No barcodes scanned")
    found, errors = lookup_many(barcodes, process="sub")
    if errors:
        raise ValueError("; ".join(errors.values()))
    items = [found[b] for b in barcodes]
    families = {it.family for it in items}
    if len(families) > 1:
        raise ValueError("Bold, Classic and Essential print on separate sheets; generate them as separate batches")
    family = families.pop()
    paths = _download_all(items)

    pieces, placements = [], []
    for i, (it, path) in enumerate(zip(items, paths)):
        info = image_info(path)
        pieces.append({"path": path, "w_pt": info["w_pt"], "h_pt": info["h_pt"], "name": it.label,
                       "src_mode": image_mode(path)})
        placements.append(Placement(index=i, sheet=i // per_sheet + 1, position=i % per_sheet + 1,
                                    x=0, y=0, w=info["w_pt"], h=info["h_pt"]))

    run_id = _claim_run_dir(f"{family}_{template}_{color}", prefix="SUB")
    out = RUNS_DIR / run_id
    (out / "files").mkdir()
    sheets = (len(pieces) + per_sheet - 1) // per_sheet
    sheet_pdfs, label_pdfs, warnings = [], [], []
    for s in range(sheets):
        chunk = pieces[s * per_sheet:(s + 1) * per_sheet]
        pdf_path = out / f"{run_id}_S{s + 1}.pdf"
        for w in build_sheet(template, color, chunk, pdf_path, pdf_path.stem, mirror=mirror):
            warnings.append(f"sheet {s + 1} {w}")
        sheet_pdfs.append(pdf_path)
        # item labels for this sheet: one 2x1" label per piece, in slot order (as HP SiteFlow prints them)
        lbl_path = out / f"{run_id}_S{s + 1}_LABELS.pdf"
        build_labels(items[s * per_sheet:(s + 1) * per_sheet], lbl_path, lbl_path.stem)
        label_pdfs.append(lbl_path)
    xlsx = out / f"{run_id}_manifest.xlsx"
    write_manifest(placements, items, xlsx, run_id)

    for p in placements:
        it, src = items[p.index], pieces[p.index]["path"]
        name = f"S{p.sheet}-{p.position}_{it.batch_number}_{_safe(it.print_code)}_{it.component_barcode}{src.suffix}"
        shutil.copyfile(src, out / "files" / name)

    converted = sum(1 for pc in pieces if pc["src_mode"] != color)
    meta = {
        "run_id": run_id,
        "process": "sub",
        "line": template,
        "family": family,
        "template": template,
        "template_title": templates[template]["title"],
        "per_sheet": per_sheet,
        "color": color,
        "mirror": bool(mirror),
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "user": user,
        "pieces": len(items),
        "sheets": sheets,
        "converted": converted,
        "warnings": warnings,
        "barcodes": barcodes,
    }
    (out / "run.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    with zipfile.ZipFile(out / f"{run_id}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in (*sheet_pdfs, *label_pdfs, xlsx):
            z.write(f, f.name)
        for f in sorted((out / "files").iterdir()):
            z.write(f, f"files/{f.name}")
    return meta


def _custom_manifest(rows, path, title):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Pieces"
    ws.append(["Sheet", "Position", "Name on sheet", "Width mm", "Height mm", "Fit to slot", "Source file"])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F2937")
    for r in rows:
        ws.append(r)
    for col, w in zip("ABCDEFG", (7, 9, 40, 10, 10, 10, 40)):
        ws.column_dimensions[col].width = w
    wb.properties.title = title
    wb.save(path)


def create_custom_run(custom, template=DEFAULT_TEMPLATE, color="CMYK", user="", mirror=True, fit=False):
    """Sublimation sheets from artwork uploaded by the team (no Pulse order): same template,
    flip and RGB/CMYK options; copies repeat an artwork; optional fit-to-slot. No item labels."""
    from .custom import item_for
    template = template or DEFAULT_TEMPLATE
    templates = registry()
    if template not in templates:
        raise ValueError(f"Unknown template {template!r}")
    color = (color or "CMYK").upper()
    if color not in ("RGB", "CMYK"):
        raise ValueError("Colour must be RGB or CMYK")
    pieces = []
    for c in custom or []:
        key = str(c.get("fetch_url") or "")
        if not key.startswith("custom://") or not cached_path(key).exists():
            raise ValueError(f"Artwork {c.get('name') or key} is no longer on the server; upload it again")
        it = item_for(key, str(c.get("name") or "Custom artwork")[:80])
        copies = max(1, min(500, int(c.get("copies") or 1)))
        for n in range(copies):
            pieces.append({"path": cached_path(key), "w_pt": it["w_pt"], "h_pt": it["h_pt"],
                           "name": it["name"], "src_mode": it["mode"], "fit": bool(fit),
                           "copy_no": n + 1, "copies": copies})
    if not pieces:
        raise ValueError("No custom artwork added")
    per_sheet = len(templates[template]["slots"])

    run_id = _claim_run_dir(f"CUSTOM_{template}_{color}", prefix="SUB")
    out = RUNS_DIR / run_id
    (out / "files").mkdir()
    sheets = (len(pieces) + per_sheet - 1) // per_sheet
    sheet_pdfs, label_pdfs, warnings, rows = [], [], [], []
    for s in range(sheets):
        chunk = pieces[s * per_sheet:(s + 1) * per_sheet]
        pdf_path = out / f"{run_id}_S{s + 1}.pdf"
        for w in build_sheet(template, color, chunk, pdf_path, pdf_path.stem, mirror=mirror):
            warnings.append(f"sheet {s + 1} {w}")
        sheet_pdfs.append(pdf_path)
        # basic 2x1" labels from the table: text, sheet position, copy n / copies
        lbl_path = out / f"{run_id}_S{s + 1}_LABELS.pdf"
        build_custom_labels([{"run_id": run_id, "pos": f"S{s + 1}-{i + 1}", "name": pc["name"],
                              "copy_no": pc["copy_no"], "copies": pc["copies"]} for i, pc in enumerate(chunk)],
                            lbl_path, lbl_path.stem)
        label_pdfs.append(lbl_path)
        for i, pc in enumerate(chunk):
            rows.append([s + 1, i + 1, pc["name"], round(pc["w_pt"] / 72 * 25.4, 1),
                         round(pc["h_pt"] / 72 * 25.4, 1), "yes" if fit else "", pc["path"].name])
    xlsx = out / f"{run_id}_manifest.xlsx"
    _custom_manifest(rows, xlsx, run_id)
    for p in {pc["path"] for pc in pieces}:
        shutil.copyfile(p, out / "files" / p.name)

    meta = {
        "run_id": run_id, "process": "sub", "custom": True, "line": template, "family": "CUSTOM",
        "template": template, "template_title": templates[template]["title"], "per_sheet": per_sheet,
        "color": color, "mirror": bool(mirror), "fit": bool(fit),
        "created": dt.datetime.now().isoformat(timespec="seconds"), "user": user,
        "pieces": len(pieces), "sheets": sheets,
        "converted": sum(1 for pc in pieces if pc["src_mode"] != color), "warnings": warnings,
        "artworks": [{"name": c.get("name"), "copies": c.get("copies", 1), "file": c.get("fetch_url")} for c in custom],
    }
    (out / "run.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    with zipfile.ZipFile(out / f"{run_id}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in (*sheet_pdfs, *label_pdfs, xlsx):
            z.write(f, f.name)
        for f in sorted((out / "files").iterdir()):
            z.write(f, f"files/{f.name}")
    return meta


def create_uv_custom_run(custom, user=""):
    """UV bed from artwork uploaded by the team (no Pulse order): File, Die and Spot PDFs + Excel,
    same right-aligned layout as LUX/Mirror. Die = each image's exact size; the die label is the
    text typed in the table. Copies repeat an artwork."""
    from types import SimpleNamespace
    from .custom import item_for
    items, pieces = [], []
    for c in custom or []:
        key = str(c.get("fetch_url") or "")
        if not key.startswith("custom://") or not cached_path(key).exists():
            raise ValueError(f"Artwork {c.get('name') or key} is no longer on the server; upload it again")
        it = item_for(key, str(c.get("name") or "Custom artwork")[:80])
        copies = max(1, min(500, int(c.get("copies") or 1)))
        path = cached_path(key)
        info = image_info(path)
        for n in range(copies):
            items.append(SimpleNamespace(
                label=it["name"], line="CUSTOM", reconcile_model=it["name"], batch_number="CUSTOM",
                order_number="", hp_order_id="", component_barcode=f"{it['component_barcode']}-{n + 1}",
                item_barcode="", print_code="", print_sku="", sku="", model="", case_type="",
                job_status="custom", order_status="", item_status="", reprint=False, reprint_reason="",
                status_updated="", fetch_url=key))
            pieces.append({"label": it["name"], "w": info["w_pt"], "h": info["h_pt"], "path": path, "info": info})
    if not pieces:
        raise ValueError("No custom artwork added")

    placements = layout(pieces)
    run_id = _claim_run_dir("CUSTOM")
    out = RUNS_DIR / run_id
    (out / "files").mkdir()
    file_pdf = out / f"{run_id}_FILE.pdf"
    die_pdf = out / f"{run_id}_DIE.pdf"
    xlsx = out / f"{run_id}_manifest.xlsx"
    build_pdfs(placements, pieces, file_pdf, die_pdf, run_id)
    sheets = max(p.sheet for p in placements)
    spot_pdfs = []
    for s in range(1, sheets + 1):
        sp = out / (f"{run_id}_SPOT.pdf" if sheets == 1 else f"{run_id}_SPOT_S{s}.pdf")
        build_spot_pdf([p for p in placements if p.sheet == s], pieces, items, sp, sp.stem)
        spot_pdfs.append(sp)
    write_manifest(placements, items, xlsx, run_id)
    for p in {pc["path"] for pc in pieces}:
        shutil.copyfile(p, out / "files" / p.name)

    meta = {
        "run_id": run_id, "process": "uv", "custom": True, "line": "CUSTOM",
        "created": dt.datetime.now().isoformat(timespec="seconds"), "user": user,
        "pieces": len(pieces), "sheets": sheets, "barcodes": [],
        "artworks": [{"name": c.get("name"), "copies": c.get("copies", 1), "file": c.get("fetch_url")} for c in custom],
    }
    (out / "run.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    with zipfile.ZipFile(out / f"{run_id}.zip", "w", zipfile.ZIP_DEFLATED) as z:
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
            metas.append(json.loads(m.read_text(encoding="utf-8")))
    return sorted(metas, key=lambda m: m["created"], reverse=True)[:limit]


def run_file(run_id, kind):
    if not RUN_ID_RE.fullmatch(run_id):
        return None
    out = RUNS_DIR / run_id
    if run_id.startswith("SUB_") and kind == "file":
        return _sheets_download(out, run_id)
    if run_id.startswith("SUB_") and kind == "labels":
        return _sheets_download(out, run_id, labels=True)
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


def _sheets_download(out, run_id, labels=False):
    """Sublimation sheet (or label) PDF; for a multi-sheet run, one ZIP holding every sheet's PDF."""
    if labels:
        pdfs = sorted(out.glob(f"{run_id}_S*_LABELS.pdf"), key=lambda p: int(p.stem.split("_S")[-1].split("_")[0]))
    else:
        pdfs = sorted((p for p in out.glob(f"{run_id}_S*.pdf") if not p.stem.endswith("_LABELS")),
                      key=lambda p: int(p.stem.rsplit("_S", 1)[1]))
    if len(pdfs) <= 1:
        return pdfs[0] if pdfs else None
    z = out / f"{run_id}_{'LABELS' if labels else 'SHEETS'}.zip"
    if not z.exists():
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in pdfs:
                zf.write(f, f.name)
    return z
