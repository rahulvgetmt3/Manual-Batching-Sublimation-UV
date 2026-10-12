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
from .runs import create_run, list_runs, run_file

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
    return {"user": _require_user(request)}


def _resolve(codes):
    """Look up barcodes and download their print files.

    Returns {"items": [...], "errors": [{"barcode", "error"}]} in the order given.
    """
    codes = normalise(codes)
    if len(codes) > MAX_BULK:
        raise HTTPException(422, f"Too many barcodes ({len(codes)}); max {MAX_BULK} per lookup")
    items, errors = lookup_many(codes)

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
def item(barcode: str, request: Request):
    _require_user(request)
    res = _resolve([barcode])
    if res["errors"]:
        return JSONResponse({"error": res["errors"][0]["error"]}, status_code=422)
    return res["items"][0]


class BulkReq(BaseModel):
    text: str


@app.post("/api/items")
def bulk_items(req: BulkReq, request: Request):
    """Bulk search: pasted barcodes separated by newlines, commas or spaces."""
    _require_user(request)
    return _resolve(parse_text(req.text))


@app.post("/api/import")
async def import_file(request: Request, file: UploadFile = File(...)):
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
    return await run_in_threadpool(_resolve, codes)


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
    barcodes: list


@app.post("/api/runs")
def new_run(req: RunReq, request: Request):
    user = _require_user(request)
    try:
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
            bg = Image.new("RGB", im.size, "white")
            bg.paste(im.convert("RGBA"), mask=im.convert("RGBA").getchannel("A"))
            bg.save(t, "JPEG", quality=80)
    return FileResponse(t, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@app.get("/healthz")
def healthz():
    return {"ok": True}
