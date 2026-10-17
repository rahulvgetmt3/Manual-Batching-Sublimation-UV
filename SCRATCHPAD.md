# Scratchpad

This is the running log of work on the UV Mix Batch portal. Notes on how things work live in [docs/claude-memory/](docs/claude-memory/); Claude's memory for this folder links there. How to run and deploy is in [README.md](README.md). The full chat is in [chat/](chat/).

**Repo:** https://github.com/rahulvgetmt3/Manual-Batching-Sublimation-UV (private; renamed from `uv-mix-batch` on 2026-10-13; local folder `~/Dev/Mix Batch UV and Sublimation`). Branch `main` holds UV Mix with the Pulse theme; the UV team's PCs still run an older copy. Branch **`sublimation`** adds Sublimation and the layout fix. It's on Rahul's Mac and gets merged when approved. `data/`, `Reference/`, `.venv` and the raw chat `.jsonl` are git-ignored.

To keep it current: after each session, add a dated entry at the top of the **Log**, add a row to **Sessions**, and update **Open items**.

## Open items

**Team testing (from 2026-10-11, on Windows PCs; team PC connected to Pulse)**
- [ ] **Print test on the printer.** Print File, Die and Spot from portal runs, including several batches and a multi-sheet run (140+ pieces). Confirm:
  - the printer accepts the new **Die PDF** (PDF 1.6, hidden Artwork layer, outlined labels). The old one, a few KB, was rejected;
  - the **Spot PDF** prints white or spot only where there's artwork, sent directly without re-saving in Photoshop;
  - the die lines up with the artwork, and the right-aligned start matches how the bed is loaded;
  - the RIP accepts the File PDF's colours, which are original RGB with no CMYK conversion.
- [ ] **Check one Mirror bed** end to end.
- [ ] **Paste-test the Reconcile sheet** (Model = `LUX-15-PL` style) into the team's Google Sheet.
- [ ] **Feedback from the team** after a full day of use.

**Move to live (after testing passes)**
- [ ] **Move the repo** `rahulvgetmt3/Manual-Batching-Sublimation-UV` to the **MT3-Global-Tech-Inc** org (GitHub › Settings › Transfer ownership).
- [ ] **Rotate the Pulse DB password**, which is exposed and now also on the team test PCs. Create a **read-only** DB user for the portal, then rebuild the team ZIP.
- [ ] **AWS hosting:** an EC2 or Lightsail instance in the DB's region, with a security-group rule to port 3306, a domain such as `uvmix.getmt3.com`, and HTTPS through Caddy. See README › Deploy.
- [ ] **Real logins:** set real `PORTAL_USERS` and a long `SECRET_KEY`, replacing the test `uvteam` login.
- [ ] **Disk:** decide how long to keep runs. A full-bed Spot PDF is about 16 MB per 5 pieces, so expect a few hundred MB for a full bed.

- [ ] **Team history visible to Rahul:** decide on a shared runs folder (OneDrive, Google Drive or network drive) for the testing period. Otherwise it comes automatically with hosting.
- [ ] **Rebuild the team ZIP** (`python3 tools/make_team_zip.py`) before giving it to any new PC. The current TEAM zip predates the UTF-8 fix.

**Sublimation (branch `sublimation`)**
- [ ] Rahul or the team check the sheet PDFs in Illustrator and on the printer: mirroring, centring, names and RGB/CMYK.
- [x] Confirmed 2026-10-12: Reconcile model = Pulse model name; any readable font for names; names may cross registration marks.
- [ ] Merge into `main` and ship the update ZIP to the teams.
- [ ] **Scan-test the Code 128 barcode** on the BATCH ID label (not scanned yet).
- [ ] **Batch number counter is per PC** until hosting: two team PCs can both print MB00001. Decide if that's OK or change the format (e.g. date-based).
- [ ] Optional: add the sheet batch number as a column in the Excel.
- [ ] Confirm with the operators that **Model-wise** should stay the default (it uses more sheets than Mix).

**Known data issues**
- [ ] **B433C9774F** (Mirror 17-P) returned 403 earlier, then downloaded fine later. Watch for other old printcloud `fetch_url`s.

## Sessions

| Dates | Machine | Session | Main topics |
|---|---|---|---|
| 2026-10-11 | Mac | `38c655b4` | HP and Pulse access check; Current Work counts; LUX file download; portal designed and built (scan, bulk, upload, LUX/Mirror batches, File/Die/Spot/Excel, history, login); fixes for full-bed bounding box, right-aligned layout, Spot as a Photoshop-style PDF (Alph block), RIP-safe Die, Reconcile `LUX-15-PL`; GitHub repo; Windows test package; team connected |
| 2026-10-12 | Mac | `38c655b4` (same session) | Pulse theme (verbatim Pulse CSS, Manual Batching dropdown), layout fix, **Sublimation**: 6UP/6UP-EXT templates, mirrored/centred sheets, names, Bold/Classic/Essential, all models, CMYK/RGB, flip toggle, any-size uploadable templates; branch `sublimation` |
| 2026-10-13 | Mac | `38c655b4` (same session) | Artworks per sheet, batching simplification, folder + GitHub repo renames |
| 2026-10-13 → 17 | Mac | `a46c2f98` | Old chat recovered after the folder rename; README covers UV + Sublimation (both branches); **Sublimation sheet batch numbers** (red MB number on sheet + BATCH ID label page); **model-wise sheets** option; team update ZIPs |

The chat is copied to [chat/](chat/). `cleanupPeriodDays` is 3650 in `~/.claude/settings.json`, so the original won't be auto-deleted either.

## Log

### 2026-10-17 (later): /simplify review + custom-artwork fix
- 4 review agents found a **real bug**: adding the Sheets option also passed `by_model` to `create_custom_run` (a find-and-replace matched both calls), so **every Sublimation custom-artwork batch failed** in the portal. It shipped in the 10-17 update ZIP and the fresh UV package. Fixed; tested this time through the portal API (login → upload → /api/runs), not only by calling Python directly.
- Cleanups: batch counter now uses an OS file lock (safe across worker processes and on Windows), so the Dockerfile is back to 2 workers; one glyph loop in labels (`_text` wraps `text_outline`), shared `_divider`, groupby for barcode bars; custom-run Excel uses the same sheet groups as the PDFs; dead JS line removed. Two runs at once on 2 workers got separate MB numbers.
- Skipped: moving colour-bar positions (`BATCH_AT`) into template detection, and a shared short template title for Python/JS. Both are bigger changes for little gain now.
- Rebuilt `dist/Manual-Batching-UPDATE.zip` and `dist/Manual-Batching-UV-TEAM.zip` (uvteam / uvteam123) with the fix.

### 2026-10-17 (later): UV team fresh package; ready to go live
- The UV team got "wrong username or password". The logins in the package were correct, so the PC's `.env` didn't match; cause not confirmed. Built a **fresh full package** `dist/Manual-Batching-UV-TEAM.zip` with login **uvteam / uvteam123** (`make_team_zip.py --password`, new option) and tested the login against the package's own `.env`. Logins file updated: `LOGINS - PRIVATE.txt` in the project folder (git-ignored) + `dist/LOGINS-private.txt`.
- Rahul is going to put the portal on a server. Before that: Dockerfile now keeps uploaded templates in `/data` (`TEMPLATES_DIR`), runs **one worker** (the batch counter is only safe within one process), and trusts Caddy's forwarded headers; added `.dockerignore`. README › **Going live on a server** rewritten step by step (8 GB RAM, read-only DB user, `.env`, Docker, counter starting at MB10001, Caddy HTTPS, updating, backups). **The Docker build hasn't been tested** (no Docker on the Mac).

### 2026-10-17: Model-wise Sublimation sheets
- Rahul: operators need one model per sheet; give a choice. Added a **Sheets** option per Sublimation order batch: **Model-wise** (default) or **Mix models** (`726582a`). Groups by Pulse model in first-seen order; the last sheet of a model may be part-filled. Custom artwork is unchanged. The Excel Pieces sheet is now sorted by sheet/position.
- Tested with 8 real Bold items over 5 models: 5 sheets model-wise vs 2 mixed; label PDFs and batch numbers follow the sheets.
- Rebuilt `dist/Manual-Batching-UPDATE.zip` (includes the 10-16 batch numbers; Setup.bat required). **Rahul sent it to the teams and it worked** (2026-10-17).

### 2026-10-16: Sublimation sheet batch numbers
- Rahul asked for a batch number top right of each Sublimation sheet, plus a page in the label PDF with the same number, so the operator knows which labels go with which sheet. He shared SiteFlow's current version (red batch ID beside the colour bar; BATCH ID label with barcode, route, date, QTY, product).
- Built it (`548fc6d`): one `MB00001`-style number per sheet (counter in `data/runs/batch_counter.txt`), red beside the colour bar, and a BATCH ID first page in each `_S{n}_LABELS.pdf` with a Code 128 barcode (`python-barcode`, new requirement). Tested on 6UP and 6UP-EXT, Pulse and custom runs.
- Rahul's first portal test failed because the Mac portal had been running since Tuesday on old code; restarted with `./start-mac.sh` and it worked.
- Rebuilt `dist/Manual-Batching-UPDATE.zip` (no credentials) for both teams; **Setup.bat is required** this time for the new barcode library.

### 2026-10-13: Old chat recovered, README for both processes
- The old session (`38c655b4`) was stored under the previous folder name (`-Users-rahulverma-Dev-Mix-Batch-UV`), so it didn't show in `claude --resume` after the rename. Copied it into the new project folder and re-exported `chat/transcript.md`.
- README rewritten to cover UV Mix and Sublimation (custom artwork, labels, artworks per sheet, history, team packages, new repo name); pushed to `sublimation` and `main` (`ba3fc30` / `8b71a0c`).

### 2026-10-13: Artworks per sheet (Sublimation)
- Added an "Artworks per sheet" option (all slots, or 1 to 5 on 6UP) for printing on fewer nesting jigs. It fills the first slots: TL, TR and so on. Tested via the API: 5 copies at 2 per sheet gave 3 sheets with labels of 2, 2 and 1, and order barcodes at 1 per sheet gave 3 sheets.
- Rebuilt `dist/Manual-Batching-UPDATE.zip` (contains no credentials) for both teams; Rahul is sending it. Still to confirm: which slots the jigs use.

### 2026-10-12: UV custom artwork + team update package
- **UV custom artwork:** the same Custom artwork tab now works on UV Mix. It builds a separate `UV_CUSTOM_…` batch with File, Die and Spot PDFs plus Excel. Each die cut is the exact image size, and the typed name is printed on the die only. Tested via the API: the cuts matched the images, and Rahul confirmed the Sublimation custom flow works well.
- **Team update:** `dist/Manual-Batching-UPDATE.zip` contains no credentials. The team copies it over their existing folder, runs Setup.bat once, starts with "Start Manual Batching.bat", then presses Ctrl+F5. Rahul is sending it to both teams. Status: all set.

### 2026-10-12: Sublimation custom artwork
- New Custom artwork tab: upload files or a link. The table shows the image next to the text printed beside it, plus copies. Batches support fit-to-slot or actual size and the same template, flip and CMYK/RGB options, with basic 2 × 1 labels per sheet.
- Tested through the API; Rahul still needs to try the screen.

### 2026-10-12: Design team running
- The Design (Sublimation) team PC is set up and **working**. It had Python 3.14 and needed 3.13 installed alongside; the docs and Setup message are updated.

### 2026-10-12: Package for the Sublimation (Design) team
- Built `dist/Manual-Batching-Sublimation-TEAM.zip` with login **DesignTeam** (the password is in the ZIP's START HERE.txt and `dist/LOGINS-private.txt`). It opens on Sublimation.
- Generic "Manual Batching" naming and `Start Manual Batching.bat` (`40906bc`). The UV team still has the older package and launcher name until they get an update.

### 2026-10-12: Sublimation item labels
- Added 2 × 1 inch item labels: one labels PDF per sheet, one label per page in slot order, and a Labels button. They copy the HP greensheet template "MB 2x1", with data from Pulse and the QR encoding the component barcode.
- **Rahul confirmed it works.**

### 2026-10-12: Any-size Sublimation templates
- Templates can now be uploaded in the portal (Manual Batching ▾ › Sublimation › Templates). Slots, name sides, and frame and QR removal are detected automatically, and pieces per sheet follow the template.
- Also: all Bold, Classic and Essential models are included (Casely-Bold-13/14/15, Casely-Bold-16e/17e, 4_Sublimation); green frames aren't printed; the defaults are 6UP Extended and CMYK.
- **The team tests only 6UP for now.** 1UP, 10UP and others are uploaded when needed.

### 2026-10-12: Sublimation built (branch `sublimation`)
- Rahul's 9-step brief, plus: Bold and Classic on separate sheets (split by case type), a flip toggle (default mirrored), names as OrderID-Model-CaseType.
- **Templates:** cleaned from the team's `.ai` files. QR codes are removed, and slots and registration marks are recorded. The SWOP profile is used for RGB/CMYK conversion and is never embedded.
- **Tested** with real barcodes. Test runs: `SUB_BOLD_6UP_RGB_20261012_02`, `SUB_CLASSIC_6UP-EXT_CMYK_20261012_01`, `SUB_CLASSIC_6UP-EXT_RGB_20261012_01` (2 sheets), `SUB_BOLD_6UP_CMYK_20261012_01` (not flipped).
- **Housekeeping:** the pending hidden-login change was moved out of `app/` into `dist/pending-admin-login.patch` and `dist/pending-admins.json` (Mac only) so it can't be committed.
- **Next:**
  - Rahul checks the sheets in Illustrator and on the printer;
  - the reconcile "Model" format for Sublimation needs confirming;
  - when approved, merge `sublimation` into `main` and send the teams an update.

### 2026-10-11 (end): Mac settings file
- Added a git-ignored `.env` for Rahul's Mac with the portal login `Rahul`, a fixed SECRET_KEY and COOKIE_SECURE=0. It holds no DB password.
- Added `./start-mac.sh`, which restarts the portal by loading `~/Dev/Pulse/.env` and then `.env`.
- The logins are listed in `dist/LOGINS-private.txt` (git-ignored, Mac only).
- **Uncommitted, decision pending:** `app/main.py` and `app/admins.json` contain an unfinished admin login that works on every copy. It was blocked as a hidden backdoor, so either finish it as a disclosed login or remove it before the next team update.

### 2026-10-11 (end): Login rename, Windows UTF-8 fix
- Rahul's Mac login was renamed `test` to **Rahul**; 34 earlier test runs were relabelled. Logins are now case-insensitive and keep the display name (`222788c`).
- **Windows mojibake fixed** (`df707b0`): the team UI showed "â¬‡ ZIP" and "Â·" because Python defaults to cp1252 on Windows. Static HTML and `run.json` are now read and written as UTF-8. Shipped as `dist/app-update.zip` (the `app` folder only), and it **worked on the team PC**.
- Rahul asked to see the team's history from his login without telling them. The options are recorded in [uv-mix-portal-overview](docs/claude-memory/uv-mix-portal-overview.md), and his choice of shared folder is pending.

### 2026-10-11 (end of day): Team connected; handover saved
- Rahul ran `tools/make_team_zip.py` and the **team PC connected to Pulse**. The team now tests on their own, with login `uvteam`; the password is in the ZIP's START HERE.txt.
- `tools/make_team_zip.py` builds `dist/UV-Mix-Batch-Windows-TEAM.zip` with a pre-filled `.env`. It contains no secrets itself; credentials are read at run time from `~/Dev/Pulse/.env`, and `dist/` is git-ignored.
- Saved memory, this scratchpad and the chat transcript, and pushed. **Next session:** pick up from **Open items**, starting with the printer results and then the move to the MT3 org and hosting.

### 2026-10-11 (later): Windows test package
- For team testing only; the live version will be hosted, and the repo moved to the MT3 org afterwards.
- Added `Setup.bat` and `Start UV Mix.bat` (both call `windows/*.ps1`), `windows/check_db.py` and [README-WINDOWS.md](README-WINDOWS.md). Each PC runs its own portal at http://localhost:8765.
- Build the ZIP with `git archive --format=zip --prefix="UV Mix Batch/" -o dist/UV-Mix-Batch-Windows.zip HEAD app requirements.txt Setup.bat "Start UV Mix.bat" windows .env.example README-WINDOWS.md`.
- **Not run on Windows yet** (there's no PowerShell on this Mac). Each PC's public IP needs the DB allowlist, and its `.env` holds the DB password, so use a read-only user.

### 2026-10-11 (later): Pushed to GitHub
- Initialised git and pushed to `rahulvgetmt3/uv-mix-batch` (first commit `18162a3`). The commit identity is set for this repo only: `rahulvgetmt3 <rahulv@getmt3.com>`.
- The repo was created under Rahul's personal account, not the MT3-Global-Tech-Inc org. Transfer it to the org later if the team needs access.

### 2026-10-11 (later): Spot PDF works; Reconcile model format
- **Spot PDF confirmed working in Photoshop** (Spot Color 1 appears). The missing piece was Photoshop's `Alph` spot-channel definition block, together with the Photoshop Producer/XMP identification. Details are in [photoshop-spot-channel-psd](docs/claude-memory/photoshop-spot-channel-psd.md).
- **Reconcile sheet:** Model now shows line + die label (`LUX-15-PL`, `MIRROR-17-PM`) instead of the Pulse model name. Test runs: `UV_LUX_20261011_28`, `UV_MIRROR_20261011_06`.
- **Still to confirm:** Spot PDF and the new Die PDF on the printer.

### 2026-10-11 (later): Spot file is a PDF again
- Rahul needs the spot file as a PDF. Added `app/spot_pdf.py`, a Photoshop-style PDF with the same page content and private round-trip data as the team's file (details in [photoshop-spot-channel-psd](docs/claude-memory/photoshop-spot-channel-psd.md)).
- **Checks on test run `UV_LUX_20261011_21`:**
  - Spot PDF is 16 MB, built in 7.5 s.
  - Spot ink equals the artwork's opacity.
  - Layer pixels equal the source files.
  - The layer block lengths are internally consistent.
- **To confirm:** it opens in Photoshop with the Spot Color 1 channel, and it prints on the printer.

### 2026-10-11 (later): Printer rejected the Die PDF
- Rahul reported that `UV_MIRROR_20261011_04`'s Die PDF wouldn't load on the printer because it was only a few KB.
- **Rebuilt it like the team's Illustrator die:**
  - PDF 1.6 instead of 1.3; transparency needs 1.4 or later;
  - all page boxes set;
  - labels as vector outlines, so no unembedded Helvetica;
  - a hidden Artwork layer plus a visible Die layer.
- The same batch was regenerated as `UV_MIRROR_20261011_05`. Its Die PDF is now about 1.3 MB. **Waiting for the printer retest.**
- B433C9774F downloaded fine this time; the earlier 403 has cleared.

### 2026-10-11: Portal built; print test next
**HP and Pulse**
- Confirmed access to both: SiteFlow API (`~/Dev/HP Siteflow/.env`) and Pulse MySQL (`~/Dev/Pulse/.env`, IP 122.176.110.84 allowlisted).
- Current Work matched SiteFlow live batches: Essential 4, Bold 7 (screen showed 2 mid-close), Classic 16, Lux 5, Screen Protector 3, iPad 1, FBM iPad 1.
- Downloaded the 5 LUX print files to `LUX_2026-10-11/`. Batch 416718 (13 PM) was overdue and had been reprinted 3 times.

**Portal** (`app/`, FastAPI, runs at `localhost:8765`, login `Rahul` / `test123`)
- **Input:** scan, paste a list, or upload CSV/XLSX with downloadable templates. Item barcodes resolve to their component. Rejected codes are listed with reasons.
- **Lookup:** one bulk Pulse query. LUX/Mirror only, from `batch_imposition`. MT3 `fetch_url` only. Exact job, order and item statuses.
- **Outputs per run:**
  - **File PDF:** artwork only, original RGB pixels and ICC, no CMYK.
  - **Die PDF:** 0.75 pt strokes plus model labels.
  - **Spot PSD:** RGB layers plus the "Spot Color 1" channel.
  - **Excel:** a Reconcile sheet (A/B/C) and a Pieces sheet.
  - All of these come in a ZIP, and runs are kept in a history.
- **Fixes after Rahul's reviews:**
  1. Labels moved to the die only.
  2. LUX and Mirror split into separate batches.
  3. Reconcile sheet in the team's format.
  4. UI: upload box fixed, History tab, last batch shown in green, colour-coded buttons.
  5. **Full-bed bounding box:** an invisible 0%-opacity frame, the same as the team's Illustrator files.
  6. **Right-aligned layout** (artwork not flipped).
  7. **Spot output:** first a PDF Separation, which Photoshop flattens, so it became a **PSD**. Then the spot channel's **polarity was fixed**, since PSD spot data is inverted.
- **Tested:** pixel-identical embedding; die boxes equal file size at 300 DPI; overflow onto sheet 2 (132 + 18 for 150 pieces); auth; bulk, CSV and XLSX imports; PSD validated with psd-tools; Rahul saw the Spot Color 1 channel in Photoshop.
- **Latest test runs:** `data/runs/UV_LUX_20261011_18` (corrected spot) and `UV_MIRROR_20261011_01`.
