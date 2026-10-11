# UV Mix Batch portal (LUX + Mirror)

Add component barcodes (or item barcodes, which resolve to their component) by:
- **Scan**: one at a time with a USB scanner.
- **Paste list**: many at once, separated by newlines, commas or spaces.
- **Upload file**: a CSV or Excel file with a `Component Barcode` column. Templates download from the Upload tab (`/api/template.xlsx`, `/api/template.csv`). If the file has no such column, every cell that looks like a barcode is used.

Rejected codes are listed with the reason: not found, not LUX or Mirror, no print file, file won't download, or a duplicate.

For a 2180 × 1220 mm UV bed, each run gives you:
- **`…_FILE.pdf`**: the MT3 print files at true size (300 DPI). Artwork only, no labels.
- **`…_DIE.pdf`**: built like the team's Illustrator die. A visible **Die** layer has 0.75 pt black strokes on each file's exact bounding box, with the model label (`15-PL`, `17-PM`, …) above each one as vector outlines, so no fonts are needed. A hidden **Artwork** layer carries the files, as in the team's file. It's PDF 1.6 with all page boxes set. The File PDF uses the same version and boxes.
- **`…_SPOT.pdf`**: a Photoshop-style PDF built like the team's spot file (`app/spot_pdf.py`). It's 2180.76 × 1221.23 mm at 300 ppi and has two parts:
  - **The printable page, read by the RIP:** a full-bed **"Spot Color 1"** separation (Indexed over Separation, white preview) drawn first, then the full-bed RGB artwork with a soft mask on top, both overprinting. Spot ink equals the artwork's opacity: full where the file is opaque, soft on edges, and none where a PNG is transparent.
  - **Photoshop's private round-trip data**, so Photoshop reopens the file with layers and the spot channel. This is CompositeImage, SpotChannels, ImageResources (300 ppi) and StandardImageFileData2, the layer data in Photoshop's large-document format with one layer per piece.

  Multi-sheet runs produce `_SPOT_S1.pdf`, `_SPOT_S2.pdf` and so on. The ink name can be changed with `SPOT_NAME`.
- **`…_manifest.xlsx`**: first sheet **Reconcile** in the team's tracking format: A = Reconcile (batch number), B = Model (Pulse model name), C = Qty., one row per batch + model, sorted by batch number. Second sheet **Pieces**: sheet, position, label, batch number, order number, HP order ID, component and item barcodes, print code and SKU, model, case type, exact Pulse **job / order / item status**, reprint and its reason, the time HP last updated the status, size and file URL.
- **`files/`**: the source files, named `S<sheet>-<pos>_<batch>_<printcode>_<barcode>`.

Only **LUX** and **Mirror** components are accepted. The product line comes from
`hp_order_items.batch_imposition` (`LUX-…` / `MIRROR-…`). The two lines print with
different methods, so the screen keeps them as separate batches, each with its own
Generate button, and the server refuses any run that mixes them. Files come from
`fetch_url`, which holds the MT3-approved print file. The customer artwork in
`hp_od_print_url` is never used.

Statuses are shown exactly as Pulse stores them. A row is highlighted only when the
job isn't `live` or the order is `cancelled`/`error`. Reprints normally sit on orders
already marked `shipped` or `complete`.

## Colour handling
The PDFs carry each file's pixels exactly as supplied. There is no CMYK conversion, no
resampling and no OutputIntent. If a PNG has an embedded ICC profile, that same profile
is attached; if not, the image is plain DeviceRGB. Transparency is kept as a soft mask.
JPEGs are embedded byte-for-byte.

## Full-bed artboard
Both PDFs carry the same invisible frame the team's Illustrator files have: a 0.75 pt
stroke round the whole 2180 × 1221 mm page at 0% opacity. It prints nothing, but
Photoshop ("Crop To: Bounding Box") and the RIP see artwork edge to edge, so files
always open at the full bed size, even when the pieces only fill one corner.

## Layout
- Pieces with the same label sit together, tallest groups first.
- **Right-aligned:** piece 1 sits in the top-right corner. Rows fill right→left and then top→bottom, with a 20 mm margin and 7 mm gaps. The print and die PDFs use identical positions.
- Each label's baseline sits 6 mm above its piece.
- When a bed is full the run continues on sheet 2, 3… (about 130 Pro Max-sized pieces fit per sheet).

To change any of these, edit the constants at the top of `app/layout.py`.

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
| `app/pulse.py` | Barcodes → items in one bulk query (LUX/Mirror check, label, statuses) |
| `app/importer.py` | Parse pasted text / CSV / Excel; import templates |
| `app/fetch.py` | Download/cache print files, read pixel size + DPI |
| `app/layout.py` | Bed packing |
| `app/pdf_build.py` | Print + die PDFs (pikepdf) |
| `app/manifest.py` | Excel manifest |
| `app/runs.py` | Builds a run folder + ZIP; run history |
| `app/main.py` | FastAPI routes + login |
| `app/static/` | Scan screen + login page |
