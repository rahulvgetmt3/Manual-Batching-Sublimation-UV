"""Turn a list of scanned component barcodes into a finished run folder + ZIP."""

import datetime as dt
import json
import os
import re
import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .custom import item_for
from .fetch import cached_file, cached_path, image_info
from .labels import build_labels, custom_label_ops, label_ops
from .layout import MM, Placement, layout
from .manifest import write_custom_manifest, write_manifest
from .pdf_build import build_pdfs
from .pulse import Item, lookup_many, normalise
from .spot_pdf import build_spot_pdf
from .sub_build import ArtCache, build_sheet
from .sub_templates import DEFAULT_TEMPLATE, registry

RUNS_DIR = Path(os.environ.get("RUNS_DIR", Path(__file__).resolve().parent.parent / "data" / "runs"))


def _safe(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-")


RUN_ID_RE = re.compile(r"(UV|SUB)_[A-Z0-9_-]+_\d{8}_\d+")   # a run folder name (no path separators)


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


def _new_run(line, prefix="UV"):
    """Claim the run folder and its files/ subfolder -> (run_id, out)."""
    run_id = _claim_run_dir(line, prefix)
    out = RUNS_DIR / run_id
    (out / "files").mkdir()
    return run_id, out


# Already-compressed files go into ZIPs as they are (deflating them again only costs time).
_STORED = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".zip"}


def _zip(path, entries):
    """entries: [(file, name in zip)]."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for f, name in entries:
            z.write(f, name, compress_type=zipfile.ZIP_STORED if Path(f).suffix.lower() in _STORED
                    else zipfile.ZIP_DEFLATED)


def _finish(out, meta, outputs):
    """Write run.json and the run ZIP (outputs + files/). Returns the full meta."""
    meta = {"run_id": out.name, **meta, "created": dt.datetime.now().isoformat(timespec="seconds")}
    (out / "run.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    _zip(out / f"{out.name}.zip", [(f, f.name) for f in outputs]
         + [(f, f"files/{f.name}") for f in sorted((out / "files").iterdir())])
    return meta


def _download_all(items):
    def _get(it):
        try:
            return cached_file(it.fetch_url)
        except Exception as e:  # noqa: BLE001 - reported per barcode
            raise ValueError(f"{it.component_barcode}: could not download print file ({e})") from e

    with ThreadPoolExecutor(8) as ex:
        return list(ex.map(_get, items))


def _custom_pieces(custom):
    """Uploaded artworks [{fetch_url, name, copies}] -> [(item dict, path, copy_no, copies)], copies expanded."""
    out = []
    for c in custom or []:
        key = str(c.get("fetch_url") or "")
        if not key.startswith("custom://") or not cached_path(key).exists():
            raise ValueError(f"Artwork {c.get('name') or key} is no longer on the server; upload it again")
        it = item_for(key, str(c.get("name") or "Custom artwork")[:80])
        copies = max(1, min(500, int(c.get("copies") or 1)))
        out += [(it, cached_path(key), n + 1, copies) for n in range(copies)]
    if not out:
        raise ValueError("No custom artwork added")
    return out


def _artworks(custom):
    return [{"name": c.get("name"), "copies": c.get("copies", 1), "file": c.get("fetch_url")} for c in custom]


# ---- UV bed (LUX / Mirror / custom): File, Die, Spot PDFs + Excel ----

def _uv_outputs(out, run_id, items, pieces):
    """Lay out and write File, Die, Spot (per sheet) PDFs and the manifest -> (placements, outputs)."""
    placements = layout(pieces)
    file_pdf, die_pdf = out / f"{run_id}_FILE.pdf", out / f"{run_id}_DIE.pdf"
    xlsx = out / f"{run_id}_manifest.xlsx"
    build_pdfs(placements, pieces, file_pdf, die_pdf, run_id)
    sheets = max(p.sheet for p in placements)
    spot_pdfs = []
    for s in range(1, sheets + 1):
        sp = out / (f"{run_id}_SPOT.pdf" if sheets == 1 else f"{run_id}_SPOT_S{s}.pdf")
        build_spot_pdf([p for p in placements if p.sheet == s], pieces, items, sp, sp.stem)
        spot_pdfs.append(sp)
    write_manifest(placements, items, xlsx, run_id)
    return placements, [file_pdf, die_pdf, *spot_pdfs, xlsx]


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
    pieces = []
    for it, path in zip(items, _download_all(items)):
        info = image_info(path)
        pieces.append({"label": it.label, "w": info["w_pt"], "h": info["h_pt"], "path": path, "info": info})

    run_id, out = _new_run(line)
    placements, outputs = _uv_outputs(out, run_id, items, pieces)
    for p in placements:
        it, src = items[p.index], pieces[p.index]["path"]
        name = f"S{p.sheet}-{p.position:03d}_{it.batch_number}_{_safe(it.print_code)}_{it.component_barcode}{src.suffix}"
        shutil.copyfile(src, out / "files" / name)
    return _finish(out, {"process": "uv", "line": line, "user": user, "pieces": len(items),
                         "sheets": max(p.sheet for p in placements), "barcodes": barcodes}, outputs)


def create_uv_custom_run(custom, user=""):
    """UV bed from artwork uploaded by the team (no Pulse order): File, Die and Spot PDFs + Excel,
    same right-aligned layout as LUX/Mirror. Die = each image's exact size; the die label is the
    text typed in the table. Copies repeat an artwork."""
    items, pieces, infos = [], [], {}
    for it, path, n, _ in _custom_pieces(custom):
        items.append(Item(label=it["name"], line="CUSTOM", reconcile_model=it["name"], batch_number="CUSTOM",
                          component_barcode=f"{it['component_barcode']}-{n}", job_status="custom",
                          fetch_url=it["fetch_url"]))
        if path not in infos:
            infos[path] = image_info(path)
        pieces.append({"label": it["name"], "w": it["w_pt"], "h": it["h_pt"], "path": path, "info": infos[path]})

    run_id, out = _new_run("CUSTOM")
    placements, outputs = _uv_outputs(out, run_id, items, pieces)
    for p in {pc["path"] for pc in pieces}:
        shutil.copyfile(p, out / "files" / p.name)
    return _finish(out, {"process": "uv", "custom": True, "line": "CUSTOM", "user": user, "pieces": len(pieces),
                         "sheets": max(p.sheet for p in placements), "barcodes": [],
                         "artworks": _artworks(custom)}, outputs)


# ---- Sublimation sheets (one PDF per sheet in a template) + item labels + Excel ----

def _per_sheet(templates, template, per):
    """Artworks per sheet PDF: the template's slot count, or fewer (1..slots) when the team prints
    on fewer nesting jigs. The first slots in fill order are used (TL, TR, ML, ...)."""
    slots = len(templates[template]["slots"])
    try:
        per = int(per or 0)
    except (TypeError, ValueError):
        per = 0
    return slots if per <= 0 else min(per, slots)


def _sub_options(template, color, per_sheet):
    """Check the Sublimation options -> (template dict, template key, color, per_sheet, meta)."""
    template = template or DEFAULT_TEMPLATE  # default: 6UP Extended (Rahul)
    templates = registry()
    if template not in templates:
        raise ValueError(f"Unknown template {template!r}")
    color = (color or "CMYK").upper()        # default: CMYK (Rahul)
    if color not in ("RGB", "CMYK"):
        raise ValueError("Colour must be RGB or CMYK")
    tpl = templates[template]
    per_sheet = _per_sheet(templates, template, per_sheet)
    meta = {"line": template, "template": template, "template_title": tpl["title"], "per_sheet": per_sheet,
            "slots": len(tpl["slots"]), "color": color}
    return tpl, template, color, per_sheet, meta


def _sub_sheets(out, run_id, tpl, color, pieces, per_sheet, mirror, labels):
    """One sheet PDF + one label PDF per `per_sheet` pieces. labels(chunk, s, start) -> (entries, ops_fn).
    -> (sheet_pdfs, label_pdfs, warnings)."""
    art = ArtCache(color)   # each artwork converted once for the whole batch
    sheet_pdfs, label_pdfs, warnings = [], [], []
    for s, start in enumerate(range(0, len(pieces), per_sheet), 1):
        chunk = pieces[start:start + per_sheet]
        pdf_path = out / f"{run_id}_S{s}.pdf"
        warnings += [f"sheet {s} {w}" for w in build_sheet(tpl, color, chunk, pdf_path, pdf_path.stem, mirror, art)]
        lbl_path = out / f"{run_id}_S{s}_LABELS.pdf"
        entries, ops_fn = labels(chunk, s, start)
        build_labels(entries, lbl_path, lbl_path.stem, ops_fn)
        sheet_pdfs.append(pdf_path)
        label_pdfs.append(lbl_path)
    return sheet_pdfs, label_pdfs, warnings


def create_sub_run(barcodes, template=DEFAULT_TEMPLATE, color="CMYK", user="", mirror=True, per_sheet=0):
    """Sublimation: one PDF per sheet in the chosen template, artwork mirrored and centred,
    names beside each piece, artwork exported as RGB or CMYK."""
    tpl, template, color, per_sheet, opts = _sub_options(template, color, per_sheet)
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

    pieces, placements = [], []
    for i, (it, path) in enumerate(zip(items, _download_all(items))):
        info = image_info(path)
        pieces.append({"path": path, "w_pt": info["w_pt"], "h_pt": info["h_pt"], "name": it.label,
                       "src_mode": info["mode"]})
        placements.append(Placement(index=i, sheet=i // per_sheet + 1, position=i % per_sheet + 1,
                                    x=0, y=0, w=info["w_pt"], h=info["h_pt"]))

    run_id, out = _new_run(f"{family}_{template}_{color}", prefix="SUB")
    # item labels: one 2x1" label per piece, in slot order (as HP SiteFlow prints them)
    sheet_pdfs, label_pdfs, warnings = _sub_sheets(
        out, run_id, tpl, color, pieces, per_sheet, mirror,
        lambda chunk, s, start: (items[start:start + len(chunk)], label_ops))
    xlsx = out / f"{run_id}_manifest.xlsx"
    write_manifest(placements, items, xlsx, run_id)
    for p in placements:
        it, src = items[p.index], pieces[p.index]["path"]
        name = f"S{p.sheet}-{p.position}_{it.batch_number}_{_safe(it.print_code)}_{it.component_barcode}{src.suffix}"
        shutil.copyfile(src, out / "files" / name)
    return _finish(out, {"process": "sub", **opts, "family": family, "mirror": bool(mirror), "user": user,
                         "pieces": len(items), "sheets": len(sheet_pdfs),
                         "converted": sum(1 for pc in pieces if pc["src_mode"] != color),
                         "warnings": warnings, "barcodes": barcodes}, [*sheet_pdfs, *label_pdfs, xlsx])


def create_custom_run(custom, template=DEFAULT_TEMPLATE, color="CMYK", user="", mirror=True, fit=False, per_sheet=0):
    """Sublimation sheets from artwork uploaded by the team (no Pulse order): same template,
    flip and RGB/CMYK options; copies repeat an artwork; optional fit-to-slot; basic 2x1 labels."""
    tpl, template, color, per_sheet, opts = _sub_options(template, color, per_sheet)
    pieces = [{"path": path, "w_pt": it["w_pt"], "h_pt": it["h_pt"], "name": it["name"], "src_mode": it["mode"],
               "fit": bool(fit), "copy_no": n, "copies": copies} for it, path, n, copies in _custom_pieces(custom)]

    run_id, out = _new_run(f"CUSTOM_{template}_{color}", prefix="SUB")
    # basic 2x1" labels from the table: text, sheet position, copy n / copies
    sheet_pdfs, label_pdfs, warnings = _sub_sheets(
        out, run_id, tpl, color, pieces, per_sheet, mirror,
        lambda chunk, s, start: ([{"run_id": run_id, "pos": f"S{s}-{i + 1}", "name": pc["name"],
                                   "copy_no": pc["copy_no"], "copies": pc["copies"]} for i, pc in enumerate(chunk)],
                                 custom_label_ops))
    xlsx = out / f"{run_id}_manifest.xlsx"
    write_custom_manifest([[i // per_sheet + 1, i % per_sheet + 1, pc["name"], round(pc["w_pt"] / MM, 1),
                            round(pc["h_pt"] / MM, 1), "yes" if fit else "", pc["path"].name]
                           for i, pc in enumerate(pieces)], xlsx, run_id)
    for p in {pc["path"] for pc in pieces}:
        shutil.copyfile(p, out / "files" / p.name)
    return _finish(out, {"process": "sub", "custom": True, **opts, "family": "CUSTOM", "mirror": bool(mirror),
                         "fit": bool(fit), "user": user, "pieces": len(pieces), "sheets": len(sheet_pdfs),
                         "converted": sum(1 for pc in pieces if pc["src_mode"] != color), "warnings": warnings,
                         "artworks": _artworks(custom)}, [*sheet_pdfs, *label_pdfs, xlsx])


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
        return _one_or_zip([p for p in out.glob(f"{run_id}_S*.pdf") if not p.stem.endswith("_LABELS")],
                           out / f"{run_id}_SHEETS.zip")
    if run_id.startswith("SUB_") and kind == "labels":
        return _one_or_zip(out.glob(f"{run_id}_S*_LABELS.pdf"), out / f"{run_id}_LABELS.zip")
    if kind == "spot":
        return _one_or_zip(out.glob(f"{run_id}_SPOT*.pdf"), out / f"{run_id}_SPOT.zip")
    name = {"zip": f"{run_id}.zip", "file": f"{run_id}_FILE.pdf",
            "die": f"{run_id}_DIE.pdf", "xlsx": f"{run_id}_manifest.xlsx"}.get(kind)
    p = out / name if name else None
    return p if p and p.exists() else None


def _sheet_no(p):
    """'…_S12.pdf' / '…_S12_LABELS.pdf' / '…_SPOT_S3.pdf' -> 12 / 12 / 3 (natural sheet order)."""
    m = re.search(r"_S(\d+)(?:_LABELS)?$", p.stem)
    return int(m.group(1)) if m else 0


def _one_or_zip(pdfs, zip_path):
    """The single PDF, or (built once) a ZIP of all of them in sheet order."""
    pdfs = sorted(pdfs, key=_sheet_no)
    if len(pdfs) <= 1:
        return pdfs[0] if pdfs else None
    if not zip_path.exists():
        _zip(zip_path, [(f, f.name) for f in pdfs])
    return zip_path
