# MT3 Manual Batching portal (UV Mix + Sublimation)

GitHub: **rahulvgetmt3/Manual-Batching-Sublimation-UV**

One portal, styled like Pulse, that turns a list of barcodes into print-ready batch files.
The **Manual Batching ▾** menu has two processes, and each one has its own **Build** and **History** pages:

| Process | Products | Output per batch |
|---|---|---|
| [**UV Mix**](#uv-mix-lux--mirror) | LUX and Mirror | File, Die and Spot PDFs on a 2180 × 1220 mm bed, Excel, ZIP |
| [**Sublimation**](#sublimation) | Bold, Classic and Essential | One mirrored sheet PDF per template sheet, 2 × 1 in labels, Excel, ZIP |

Both processes accept barcodes the same way, and both have a **Custom artwork** tab for files that aren't Pulse orders.

> **Branches:** `sublimation` has the full portal (UV Mix + Sublimation) and is the branch to use.
> `main` holds the UV Mix version and the notes, until Sublimation is approved and merged.

## Adding items (both processes)
Add component barcodes (or item barcodes, which resolve to their component) by:
- **Scan**: one at a time with a USB scanner.
- **Paste list**: many at once, separated by newlines, commas or spaces.
- **Upload file**: a CSV or Excel file with a `Component Barcode` column. Templates download from the Upload tab (`/api/template.xlsx`, `/api/template.csv`). If the file has no such column, every cell that looks like a barcode is used.
- **Custom artwork**: upload PNG/JPG/TIFF/WebP files or paste a direct link. A table shows each image beside an editable **name** and **Copies**. Custom artwork always goes into its own batch, separate from Pulse orders.

Rejected codes are listed with the reason, for example: not found, wrong product for this process, no print file, file won't download, or a duplicate.

Print files come from `fetch_url`, which holds the MT3-approved print file. The customer artwork in `hp_od_print_url` is never used. Statuses are shown exactly as Pulse stores them; a row is highlighted only when the job isn't `live` or the order is `cancelled`/`error`. Reprints normally sit on orders already marked `shipped` or `complete`.

## UV Mix (LUX + Mirror)
Only **LUX** and **Mirror** components are accepted. The product line comes from
`hp_order_items.batch_imposition` (`LUX-…` / `MIRROR-…`). The two lines print with
different methods, so the screen keeps them as separate batches, each with its own
Generate button, and the server refuses any run that mixes them.

For a 2180 × 1220 mm UV bed, each run gives you:
- **`…_FILE.pdf`**: the MT3 print files at true size (300 DPI). Artwork only, no labels.
- **`…_DIE.pdf`**: built like the team's Illustrator die. A visible **Die** layer has 0.75 pt black strokes on each file's exact bounding box, with the model label (`15-PL`, `17-PM`, …) above each one as vector outlines, so no fonts are needed. A hidden **Artwork** layer carries the files, as in the team's file. It's PDF 1.6 with all page boxes set. The File PDF uses the same version and boxes.
- **`…_SPOT.pdf`**: a Photoshop-style PDF built like the team's spot file (`app/spot_pdf.py`). It's 2180.76 × 1221.23 mm at 300 ppi and has two parts:
  - **The printable page, read by the RIP:** a full-bed **"Spot Color 1"** separation (Indexed over Separation, white preview) drawn first, then the full-bed RGB artwork with a soft mask on top, both overprinting. Spot ink equals the artwork's opacity: full where the file is opaque, soft on edges, and none where a PNG is transparent.
  - **Photoshop's private round-trip data**, so Photoshop reopens the file with layers and the spot channel. This is CompositeImage, SpotChannels, ImageResources (300 ppi) and StandardImageFileData2, the layer data in Photoshop's large-document format with one layer per piece.

  Multi-sheet runs produce `_SPOT_S1.pdf`, `_SPOT_S2.pdf` and so on. The ink name can be changed with `SPOT_NAME`.
- **`…_manifest.xlsx`**: first sheet **Reconcile** in the team's tracking format: A = Reconcile (batch number), B = Model (Pulse model name), C = Qty., one row per batch + model, sorted by batch number. Second sheet **Pieces**: sheet, position, label, batch number, order number, HP order ID, component and item barcodes, print code and SKU, model, case type, exact Pulse **job / order / item status**, reprint and its reason, the time HP last updated the status, size and file URL.
- **`files/`**: the source files, named `S<sheet>-<pos>_<batch>_<printcode>_<barcode>`.

**UV custom artwork** goes into its own `UV_CUSTOM_…` batch with the same File, Die and Spot PDFs + Excel. Each die cut is the image's exact size at its DPI. The typed name is printed above it on the die only, and shrinks if it is wider than the piece. In the Excel, Reconcile shows `CUSTOM` and Model shows the typed name.

### Colour handling
The PDFs carry each file's pixels exactly as supplied. There is no CMYK conversion, no
resampling and no OutputIntent. If a PNG has an embedded ICC profile, that same profile
is attached; if not, the image is plain DeviceRGB. Transparency is kept as a soft mask.
JPEGs are embedded byte-for-byte.

### Full-bed artboard
Both PDFs carry the same invisible frame the team's Illustrator files have: a 0.75 pt
stroke round the whole 2180 × 1221 mm page at 0% opacity. It prints nothing, but
Photoshop ("Crop To: Bounding Box") and the RIP see artwork edge to edge, so files
always open at the full bed size, even when the pieces only fill one corner.

### Layout
- Pieces with the same label sit together, tallest groups first.
- **Right-aligned:** piece 1 sits in the top-right corner. Rows fill right→left and then top→bottom, with a 20 mm margin and 7 mm gaps. The print and die PDFs use identical positions.
- Each label's baseline sits 6 mm above its piece.
- When a bed is full the run continues on sheet 2, 3… (about 130 Pro Max-sized pieces fit per sheet).

To change any of these, edit the constants at the top of `app/layout.py`.

## Sublimation
Sublimation items are **all Bold, Classic and Essential items**, every model, on any imposition: `Casely6up_*`, `Casely-Bold-6up-Extended`, `Casely-Bold-13/14/15`, `Casely-Bold-16e/17e`, `6up_Sublimation`, `4_Sublimation`, and so on. LUX, Mirror, iPad, Laptop/MacBook, Kindle and Clear generic cases are refused.

- **Batches:** one per family (Bold, Classic and Essential never share a sheet). Each batch has these controls:
  - **Template:** any template; the default is **6UP Extended**.
  - **Export:** **CMYK** (the default) or RGB.
  - **Flip artwork:** on by default, giving mirrored artwork.
  - **Artworks per sheet:** 1 up to the template's slot count, for printing on fewer nesting jigs. The first slots are filled in order (TL, TR, ML, …); the rest stay empty. Labels and positions follow the chosen count.
- **Output:**
  - one PDF per sheet (`…_S1.pdf`, `…_S2.pdf`, …);
  - **2 × 1 in item labels**, one PDF per sheet (`…_S1_LABELS.pdf`), one label per piece in slot order. They copy the HP SiteFlow greensheet template "MB 2x1": order number, source, code, description, item, customer name, quantity, and a QR of the component barcode. Text and QR are vector, so no fonts are needed;
  - an Excel (Reconcile + Pieces) and a ZIP of everything.
- **Sheet batch numbers:** every sheet gets its own batch number (`MB00001`, `MB00002`, …; they never repeat, the last one used is in `data/runs/batch_counter.txt`). It's printed in red just right of the colour bar, like SiteFlow's batch ID, and the **first page of that sheet's label PDF** is a batch label with the same number, a Code 128 barcode, the route (Bold / Classic / Essential / Custom), date, quantity, product, "Sheet n of N" and the sheet's file name, so the operator can match labels to sheets. On uploaded templates the number goes top right, above the slots.
- **Placement:** artwork at true size (300 DPI), centred in its slot and mirrored with the placement matrix only. The `OrderID-Model-CaseType` name sits beside each piece, reading bottom to top. Names are centred on the slot and may cross registration marks.
- **Colour:** files already in the chosen mode go in untouched. Others are converted with the team's **U.S. Web Coated (SWOP) v2** + sRGB (relative colorimetric + BPC), and **no profile is embedded**. Template marks stay as they are in the template.
- **Custom artwork:** the typed name is printed beside the piece, and **Copies** repeats it. Each custom batch can place artwork at **actual size** or **fit to slot** (scaled proportionally, never stretched), with the same template, flip, CMYK/RGB and artworks-per-sheet options, plus basic 2 × 1 labels.
- **Templates:** any size (1UP, 6UP, 10UP, …). Upload them under **Manual Batching ▾ › Sublimation › Templates**: a dieline PDF, or an `.ai` with PDF compatibility, without artwork, with one stroked rectangle per piece. The system detects:
  - the slots;
  - the name sides;
  - the frames, QR codes and sample codes, which are not printed.

  Built-in templates are 6UP and 6UP Extended (from `Reference/Sublimation/`). Rebuild them with `.venv/bin/python tools/build_sub_templates.py`. Uploaded templates are stored in `data/templates/sublimation/`.

## History
**Manual Batching ▾ › UV Mix / Sublimation › History** lists every generated batch for that process, with search and a filter, and links to download its files again. Runs are kept in `data/runs/` (or `RUNS_DIR`).

## Run locally
**On Rahul's Mac:** run `./start-mac.sh`. It reads the DB login from `~/Dev/Pulse/.env` and the portal settings (logins, key) from this folder's git-ignored `.env`, then opens http://localhost:8765.

**Anywhere else:**
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env        # fill in DB + PORTAL_USERS + SECRET_KEY, COOKIE_SECURE=0
set -a; source .env; set +a
.venv/bin/uvicorn app.main:app --port 8765
# open http://localhost:8765
```

Optional settings (all in `.env.example`): `RUNS_DIR`, `CACHE_DIR`, `TEMPLATES_DIR`, `SPOT_NAME`, and `DEFAULT_PROCESS` (`uv` or `sub`, the page a fresh browser opens on).

## Team test packages (Windows)
The teams test on their own Windows PCs; see [README-WINDOWS.md](README-WINDOWS.md) for their steps (`Setup.bat`, then `Start Manual Batching.bat`).

Only Rahul builds the team ZIPs, on his Mac, because they include a filled-in `.env`:
```bash
python3 tools/make_team_zip.py                                   # UV team (opens on UV Mix)
python3 tools/make_team_zip.py --login DesignTeam --process sub \
    --out Manual-Batching-Sublimation-TEAM.zip                    # Sublimation (design) team
```
The ZIPs land in the git-ignored `dist/` folder. Share them with the team only, never on GitHub.

## Deploy (cloud)
1. Create a small Linux server, such as an AWS Lightsail or EC2 t3.small, in the same AWS region as the Pulse DB.
2. Allow that server's security group or IP to reach the DB on port 3306.
3. Create a **read-only** MySQL user for the portal.
4. Install Docker, copy this folder over, then run:
   ```bash
   docker build -t uvmix .
   docker run -d --name uvmix --restart unless-stopped --env-file .env \
     -v /srv/uvmix-data:/data -p 127.0.0.1:8000:8000 uvmix
   ```
5. Put HTTPS in front of it. With Caddy, `uvmix.getmt3.com { reverse_proxy 127.0.0.1:8000 }` is enough.
6. Point a DNS record (for example `uvmix.getmt3.com`) at the server.

Runs and downloaded files are stored in `/data`. Back it up, or prune old runs from time to time.

## Files
| Path | Purpose |
|---|---|
| `app/main.py` | FastAPI routes + login |
| `app/pulse.py` | Barcodes → items in one bulk query (product check, label, statuses) |
| `app/importer.py` | Parse pasted text / CSV / Excel; import templates |
| `app/fetch.py` | Download/cache print files, read pixel size + DPI |
| `app/custom.py` | Custom artwork: uploaded files or links, cached like Pulse print files |
| `app/runs.py` | Builds a run folder + ZIP for either process; run history |
| `app/layout.py` | UV bed packing |
| `app/pdf_build.py` | UV File + Die PDFs (pikepdf) |
| `app/spot_pdf.py` | UV Spot PDF (Photoshop-style, "Spot Color 1") |
| `app/manifest.py` | Excel manifest (Reconcile + Pieces) |
| `app/sub_templates.py` | Sublimation templates: detect slots/names, clean, registry (built-in + uploaded) |
| `app/sub_build.py` | Sublimation sheet PDFs (mirror, centre, names, fit-to-slot, RGB/CMYK) |
| `app/labels.py` | Sublimation 2 × 1 in item labels |
| `app/static/` | Build/History screen (`index.html`) + login page |
| `app/static/pulse-shell.css` | Pulse's own CSS (copied verbatim) so the UI matches and ports into Pulse |
| `tools/build_sub_templates.py` | Rebuild built-in 6UP / 6UP-EXT templates from the team's .ai files |
| `tools/make_team_zip.py` | Rahul runs it: Windows test package with pre-filled `.env` (git-ignored `dist/`) |
| `Setup.bat`, `Start Manual Batching.bat`, `windows/` | Windows setup, DB check and launcher |
| `start-mac.sh` | Start the portal on Rahul's Mac (DB login from `~/Dev/Pulse/.env`, portal settings from `.env`) |
| `chat/`, `SCRATCHPAD.md`, `docs/claude-memory/` | Notes: chat transcript, work log and open items, Claude's memory |
