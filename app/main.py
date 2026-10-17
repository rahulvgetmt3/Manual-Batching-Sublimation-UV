"""MT3 UV Mix Batch portal: scan LUX / Mirror components, get print + die PDFs."""

import hmac
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer
from PIL import Image
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from .fetch import cached_file, cached_path, image_info
from .importer import parse_text, parse_upload, template_csv, template_xlsx
from .layout import MM, layout
from .pulse import LookupError_, lookup_many, normalise
from .runs import create_custom_run, create_run, create_uv_custom_run, create_sub_run, list_runs, run_file
from . import custom as cust
from . import sub_templates as subt
import tempfile

MAX_BULK = 2000

STATIC = Path(__file__).resolve().parent / "static"
SESSION_COOKIE = "uvmix_session"
SESSION_MAX_AGE = 12 * 3600

app = FastAPI(title="MT3 UV Mix Batch", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
_signer = URLSafeTimedSerializer(os.environ.get("SECRET_KEY", "dev-only-change-me"), salt="uvmix")


def _users():
    """PORTAL_USERS="alice:pass1,bob:pass2"."""
    out = {}
    for pair in os.environ.get("PORTAL_USERS", "").split(","):
        if ":" in pair:
            u, p = pair.split(":", 1)
            out[u.strip().lower()] = (u.strip(), p.strip())  # login is case-insensitive; keep display name
    return out


def _current_user(request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        return _signer.loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None


def _require_user(request):
    user = _current_user(request)
    if not user:
        raise HTTPException(401, "Not logged in")
    return user


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return (STATIC / "login.html").read_text(encoding="utf-8")


@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    found = _users().get(username.strip().lower())
    if not found or not hmac.compare_digest(found[1], password):
        return RedirectResponse("/login?error=1", status_code=303)
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(SESSION_COOKIE, _signer.dumps(found[0]), max_age=SESSION_MAX_AGE,
                    httponly=True, samesite="lax", secure=os.environ.get("COOKIE_SECURE", "1") == "1")
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    if not _current_user(request):
        return RedirectResponse("/login", status_code=303)
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/me")
def me(request: Request):
    # DEFAULT_PROCESS (uv|sub) picks the page a fresh browser opens on, e.g. 'sub' for the Sublimation team
    return {"user": _require_user(request), "default_process": _process(os.environ.get("DEFAULT_PROCESS", "uv"))}


def _process(p):
    """'uv' (LUX & Mirror) or 'sub' (Sublimation 6UP)."""
    return "sub" if (p or "").lower() == "sub" else "uv"


def _resolve(codes, process="uv"):
    """Look up barcodes and download their print files.

    Returns {"items": [...], "errors": [{"barcode", "error"}]} in the order given.
    """
    codes = normalise(codes)
    if len(codes) > MAX_BULK:
        raise HTTPException(422, f"Too many barcodes ({len(codes)}); max {MAX_BULK} per lookup")
    items, errors = lookup_many(codes, process)

    def _with_size(code):
        it = items[code]
        try:
            info = image_info(cached_file(it.fetch_url))
        except Exception as e:  # noqa: BLE001 - shown to the operator
            return code, None, f"{code}: could not download print file ({e})"
        d = it.to_dict()
        d.update(w_pt=info["w_pt"], h_pt=info["h_pt"], w_mm=round(info["w_pt"] / MM, 1),
                 h_mm=round(info["h_pt"] / MM, 1), dpi=info["dpi"][0], px=info["px"])
        return code, d, None

    with ThreadPoolExecutor(8) as ex:
        sized = {c: (d, err) for c, d, err in ex.map(_with_size, list(items))}

    out_items, out_errors, seen = [], [], set()
    for c in codes:
        if c in errors:
            out_errors.append({"barcode": c, "error": errors[c]})
            continue
        d, err = sized[c]
        if err:
            out_errors.append({"barcode": c, "error": err})
        elif d["component_barcode"] in seen:
            out_errors.append({"barcode": c, "error": f"{c}: listed twice"})
        else:
            seen.add(d["component_barcode"])
            out_items.append(d)
    return {"items": out_items, "errors": out_errors}


@app.get("/api/item/{barcode}")
def item(barcode: str, request: Request, process: str = "uv"):
    _require_user(request)
    res = _resolve([barcode], _process(process))
    if res["errors"]:
        return JSONResponse({"error": res["errors"][0]["error"]}, status_code=422)
    return res["items"][0]


class BulkReq(BaseModel):
    text: str


@app.post("/api/items")
def bulk_items(req: BulkReq, request: Request, process: str = "uv"):
    """Bulk search: pasted barcodes separated by newlines, commas or spaces."""
    _require_user(request)
    return _resolve(parse_text(req.text), _process(process))


@app.post("/api/import")
async def import_file(request: Request, file: UploadFile = File(...), process: str = "uv"):
    _require_user(request)
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        return JSONResponse({"error": "File too large (max 10 MB)"}, status_code=422)
    try:
        codes = parse_upload(file.filename, data)
    except Exception as e:  # noqa: BLE001 - bad upload shown to the operator
        return JSONResponse({"error": f"Could not read {file.filename}: {e}"}, status_code=422)
    if not codes:
        return JSONResponse({"error": f"No barcodes found in {file.filename}"}, status_code=422)
    return await run_in_threadpool(_resolve, codes, _process(process))


@app.get("/api/template.{fmt}")
def template(fmt: str, request: Request):
    _require_user(request)
    if fmt == "csv":
        return Response(template_csv(), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="uv-mix-barcodes-template.csv"'})
    if fmt == "xlsx":
        return Response(template_xlsx(),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": 'attachment; filename="uv-mix-barcodes-template.xlsx"'})
    raise HTTPException(404, "Not found")


class LayoutReq(BaseModel):
    pieces: list  # [{label, w, h}] in points


@app.post("/api/layout")
def preview_layout(req: LayoutReq, request: Request):
    _require_user(request)
    if not req.pieces:
        return {"sheets": 0, "per_sheet": []}
    try:
        pl = layout([{"label": p["label"], "w": float(p["w"]), "h": float(p["h"])} for p in req.pieces])
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=422)
    sheets = max(p.sheet for p in pl)
    return {"sheets": sheets, "per_sheet": [sum(1 for p in pl if p.sheet == s) for s in range(1, sheets + 1)]}


class RunReq(BaseModel):
    barcodes: list = []    # empty for a custom-artwork batch
    process: str = "uv"
    template: str = "6UP-EXT"  # sublimation: 6UP / 6UP-EXT (default Extended)
    color: str = "CMYK"        # sublimation: RGB / CMYK (default CMYK)
    mirror: bool = True    # sublimation: flip artwork (default on)
    custom: list = []      # UV or Sublimation: uploaded artwork [{fetch_url, name, copies}] instead of barcodes
    fit: bool = False      # sublimation custom: scale artwork to fit the slot
    per_sheet: int = 0     # sublimation: artworks per sheet PDF (0 = every slot; fewer for fewer jigs)
    by_model: bool = False  # sublimation orders: one model per sheet (else models mixed on a sheet)


@app.post("/api/runs")
def new_run(req: RunReq, request: Request):
    user = _require_user(request)
    try:
        if _process(req.process) == "sub" and req.custom:
            return create_custom_run(req.custom, req.template, req.color, user=user, mirror=req.mirror, fit=req.fit,
                                     per_sheet=req.per_sheet)
        if _process(req.process) == "sub":
            return create_sub_run([str(b) for b in req.barcodes], req.template, req.color, user=user, mirror=req.mirror,
                                  per_sheet=req.per_sheet, by_model=req.by_model)
        if req.custom:
            return create_uv_custom_run(req.custom, user=user)
        return create_run([str(b) for b in req.barcodes], user=user)
    except (LookupError_, ValueError) as e:
        return JSONResponse({"error": str(e)}, status_code=422)


@app.get("/api/runs")
def runs(request: Request):
    _require_user(request)
    return list_runs()


@app.get("/runs/{run_id}/{kind}")
def download(run_id: str, kind: str, request: Request):
    _require_user(request)
    p = run_file(run_id, kind)
    if not p:
        raise HTTPException(404, "Not found")
    return FileResponse(p, filename=p.name)


@app.get("/api/thumb")
def thumb(url: str, request: Request):
    """Small JPEG preview of an already-downloaded print file (never fetches)."""
    _require_user(request)
    path = cached_path(url)
    if not path.exists():
        raise HTTPException(404, "Not cached")
    t = path.with_suffix(".thumb.jpg")
    if not t.exists():
        with Image.open(path) as im:
            im.thumbnail((160, 320))
            rgba = im.convert("RGBA")
            bg = Image.new("RGB", im.size, "white")
            bg.paste(rgba, mask=rgba.getchannel("A"))
            bg.save(t, "JPEG", quality=80)
    return FileResponse(t, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@app.post("/api/sub/custom/files")
async def custom_files(request: Request, files: list[UploadFile] = File(...)):
    """Custom artwork from the computer: one or more image files."""
    _require_user(request)
    items, errors = [], []
    for f in files:
        data = await f.read()
        try:
            items.append(await run_in_threadpool(cust.save_bytes, data, f.filename))
        except cust.CustomError as e:
            errors.append({"barcode": f.filename, "error": str(e)})
    return {"items": items, "errors": errors}


class UrlReq(BaseModel):
    url: str


@app.post("/api/sub/custom/url")
def custom_url(req: UrlReq, request: Request):
    """Custom artwork from a link (direct image URL; Dropbox share links work too)."""
    _require_user(request)
    try:
        return {"items": [cust.save_url(req.url)], "errors": []}
    except cust.CustomError as e:
        return {"items": [], "errors": [{"barcode": req.url, "error": str(e)}]}


@app.get("/api/sub/templates")
def sub_templates(request: Request):
    """All Sublimation templates (built-in + uploaded), default first."""
    _require_user(request)
    reg = subt.registry()
    keys = sorted(reg, key=lambda k: (k != subt.DEFAULT_TEMPLATE, not reg[k].get("builtin"), k))
    return {"default": subt.DEFAULT_TEMPLATE, "templates": [subt.summary(reg[k]) for k in keys]}


@app.post("/api/sub/templates")
async def upload_sub_template(request: Request, name: str = Form(...), title: str = Form(""),
                              file: UploadFile = File(...)):
    """Upload a dieline (PDF / PDF-compatible .ai, without artwork); slots are detected automatically."""
    _require_user(request)
    try:
        key = subt.safe_key(name)
    except subt.TemplateError as e:
        return JSONResponse({"error": str(e)}, status_code=422)
    reg = subt.registry()
    if key in reg and reg[key].get("builtin"):
        return JSONResponse({"error": f"{key} is a built-in template; choose another name"}, status_code=422)
    data = await file.read()
    if len(data) > 200 * 1024 * 1024:
        return JSONResponse({"error": "File too large (max 200 MB)"}, status_code=422)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        meta = await run_in_threadpool(subt.process, tmp_path, key, title.strip() or f"Sublimation {key}", subt.USER_DIR)
    except subt.TemplateError as e:
        return JSONResponse({"error": str(e)}, status_code=422)
    finally:
        os.unlink(tmp_path)
    meta.update(builtin=False)
    return subt.summary(meta)


@app.delete("/api/sub/templates/{key}")
def delete_sub_template(key: str, request: Request):
    _require_user(request)
    try:
        subt.delete(key)
    except subt.TemplateError as e:
        return JSONResponse({"error": str(e)}, status_code=422)
    return {"ok": True}


@app.get("/healthz")
def healthz():
    return {"ok": True}
