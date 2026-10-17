# Manual Batching: developer handover

This is for the Pulse developers who will integrate Manual Batching into Pulse.
[README.md](README.md) covers what the portal does for operators and how to run and deploy it. This file covers how it's built and what integrating it involves.

## What it is
A small **Python 3.10–3.13 / FastAPI** service, about 3,600 lines, with a single-page UI in plain JS (`app/static/index.html`). Operators scan Pulse component barcodes, and it builds print-ready batch files for two processes:

| Process | Items | Output per run |
|---|---|---|
| **UV Mix** | LUX and Mirror (`hp_order_items.batch_imposition` `LUX-…` / `MIRROR-…`) | File PDF, Die PDF, Photoshop-style Spot PDF ("Spot Color 1"), Excel, ZIP |
| **Sublimation** | Bold / Classic / Essential, every model | One mirrored sheet PDF per template sheet, 2 × 1 in label PDFs per sheet, Excel, ZIP |

The print team has approved the output formats against their Illustrator/Photoshop files and the RIP. The rules behind them are in `docs/claude-memory/` (for example `sublimation-rules.md`, `photoshop-spot-channel-psd.md`, `pdf-full-bed-bounding-box.md`). **Please keep the PDF output byte-compatible.** If a change alters the output, check it with the print team.

## Recommended integration
**Keep this service as the "batching engine" and let Pulse provide the screens and the login.**
- The PDF work depends on Python libraries with no real JS equivalent: `pikepdf`/qpdf (PDF structure, optional-content layers, Photoshop private data), Pillow + LittleCMS (U.S. Web Coated SWOP v2 conversion), fontTools (text as vector outlines), segno and python-barcode (QR and Code 128). A rewrite would be a large job and would need the print team to sign off again.
- The UI already uses **Pulse's own CSS** (`app/static/pulse-shell.css`, copied verbatim from Pulse's stylesheet) and Pulse class names (`.top-nav*`, `.cd-*`, `.nordic-table*`). The **Manual Batching ▾** menu and its pages (UV Mix and Sublimation, each with Build batch and History, plus Sublimation › Templates) can be rebuilt as React pages with the same markup.
- **Auth:** today it's a simple username/password cookie (`PORTAL_USERS` in `.env`, `app/main.py` `_users` / `_current_user`). Replace it with Pulse's session or JWT. Every route calls `_require_user(request)`, so that one function is the hook. Behind a Pulse gateway it can trust a forwarded user header instead.

Options, from least to most work:
1. **Link or iframe:** deploy as in README › "Going live on a server" and add a Pulse menu entry pointing at it. Fastest, but the login is separate.
2. **API service (recommended):** Pulse React pages call the JSON API below, and the service runs on the internal network with Pulse auth.
3. **Store batches in the Pulse DB:** add tables for runs, sheets and batch numbers (see "State" below) so batches appear on Pulse order pages and the MB counter lives in MySQL.

## Pulse DB access (read-only today)
`app/pulse.py` runs **one bulk SELECT** per lookup, keyed by component or item barcode:

```
hp_order_items i                 component_barcode, item_barcode, fetch_url, sku, model, case_type,
                                 batch_imposition, hp_od_code, hp_od_print_sku, item_status,
                                 description, item_type, quantity
JOIN hp_orders o ON o.id = i.hp_order_id      order_id, source_id, source, order_status, ship_to_name
LEFT JOIN hp_jobs j ON j.barcode = i.component_barcode
                                 full_batch_number, status, reprint, reprint_reason, hp_updated_at
```
- **Print file:** `hp_order_items.fetch_url`, the MT3-approved print file. `hp_od_print_url` (customer artwork) is never used.
- **Product rules:**
  - UV Mix accepts only LUX and Mirror, and a run never mixes the two.
  - Sublimation accepts every Bold, Classic and Essential item. LUX, Mirror, iPad, Laptop/MacBook, Kindle and clear generic cases are hard-blocked.
  - Code: `is_sublimation`, `sub_family`, `sub_blocked`.
- **Settings:** `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`. Use a **read-only** user.

## JSON API (`app/main.py`)
Every route except `/login` and `/healthz` needs a logged-in user.

| Method & path | Purpose |
|---|---|
| `GET /api/item/{barcode}?process=uv\|sub` | Look up one barcode. Returns the item, or the reason it's rejected. |
| `POST /api/items?process=…` `{barcodes:[…]}` | Bulk lookup for a pasted list |
| `POST /api/import?process=…` (multipart `file`) | Barcodes from a CSV or XLSX file |
| `GET /api/template.xlsx` / `.csv` | Empty upload template |
| `POST /api/layout` `{pieces:[{label,w,h}]}` | UV bed preview: sheets and pieces per sheet |
| `POST /api/runs` | **Generate a batch.** See the body below. |
| `GET /api/runs` | Run history (`run.json` metadata) |
| `GET /runs/{run_id}/{kind}` | Download. `kind`: `zip`, `file`, `die`, `spot`, `xlsx`, `labels`. Multi-sheet files come as a ZIP. |
| `GET /api/thumb?url=…` | Artwork thumbnail |
| `POST /api/sub/custom/files` / `/api/sub/custom/url` | Upload custom artwork (no Pulse order) → `custom://…` keys |
| `GET/POST /api/sub/templates`, `DELETE /api/sub/templates/{key}` | Sublimation templates: built-in 6UP and 6UP Extended, plus uploaded dielines |
| `GET /api/me` | Current user and the default process |
| `GET /healthz` | `{"ok": true}` |

`POST /api/runs` body (`RunReq`):
```json
{"process": "sub", "barcodes": ["B433…"], "template": "6UP-EXT", "color": "CMYK",
 "mirror": true, "per_sheet": 0, "by_model": true,
 "custom": [{"fetch_url": "custom://….png", "name": "text", "copies": 2}], "fit": false}
```
- **Process:** `uv` uses only `barcodes` or `custom`.
- **`per_sheet`:** 0 means every template slot.
- **`by_model`:** one model per sheet. It's the default; `false` mixes models.

The response is the run metadata: `run_id`, `sheets`, `batches` (MB numbers per sheet), `warnings` and so on.

## Code map
| File | Role |
|---|---|
| `app/main.py` | Routes, login, request models |
| `app/pulse.py` | Pulse lookup and the product rules |
| `app/fetch.py` | Download and cache print files, read pixel size and DPI |
| `app/custom.py` | Custom artwork uploads (`custom://` cache keys) |
| `app/runs.py` | Builds a run folder (PDFs, Excel, ZIP), run history, sheet grouping, MB batch-number counter |
| `app/layout.py` | UV bed packing (2180 × 1220 mm, right-aligned, 20 mm margin, 7 mm gaps) |
| `app/pdf_build.py` | UV File and Die PDFs |
| `app/spot_pdf.py` | UV Spot PDF with Photoshop round-trip data |
| `app/sub_templates.py` | Sublimation templates: slot and name detection, registry |
| `app/sub_build.py` | Sublimation sheet PDFs (mirror, centre, names, CMYK/RGB, red batch number) |
| `app/labels.py` | 2 × 1 in item labels and the BATCH ID label (copies SiteFlow's "MB 2x1" greensheet) |
| `app/manifest.py` | Excel (Reconcile + Pieces) |
| `app/static/` | UI (`index.html`), login page, Pulse CSS |
| `tests/test_smoke.py` | Checks that need no DB: request → builder arguments, sheet grouping, batch counter |

## State (files today, could move to the Pulse DB)
Everything lives under `data/`, or `/data` in Docker (`RUNS_DIR`, `CACHE_DIR`, `TEMPLATES_DIR`):
- `runs/<RUN_ID>/`: the outputs plus `run.json` (who, when, options, barcodes, sheet batch numbers). Run ids look like `UV_LUX_20261017_01` or `SUB_BOLD_6UP-EXT_CMYK_20261017_01`.
- `runs/batch_counter.txt`: the last **MB** sheet batch number issued. It's protected by an OS file lock and replaced atomically. Keep `/data` on a local disk, not NFS or SMB. In a Pulse table this would become an auto-increment or sequence.
- `cache/`: downloaded print files and custom uploads.
- `templates/sublimation/`: uploaded Sublimation templates.

## Run and check
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # DB_* (read-only user), PORTAL_USERS, SECRET_KEY, COOKIE_SECURE=0
set -a; source .env; set +a
.venv/bin/uvicorn app.main:app --port 8765
.venv/bin/python tests/test_smoke.py
```
Docker: see README › "Going live on a server". The Dockerfile runs one worker because big runs hold several GB of image data.

## Things to know
- **Text encoding:** read and write text files with `encoding="utf-8"`. Windows otherwise defaults to cp1252.
- **Single folder per run:** run folders are claimed with an atomic `mkdir`, and the batch counter uses a file lock. Both are safe with several workers on one host.
- **Operator rules:** these come from the print team and are written down in `docs/claude-memory/`, for example right-aligned beds, names that may cross registration marks, and no colour profile embedded in converted images. Treat them as requirements.
- **Repo contents:** `chat/` and `SCRATCHPAD.md` are working notes (the design conversation and a log). Developers don't need them.
