# Scratchpad

This is the running log of work on the UV Mix Batch portal. Notes on how things work live in [docs/claude-memory/](docs/claude-memory/); Claude's memory for this folder links there. How to run and deploy is in [README.md](README.md). The full chat is in [chat/](chat/).

**Repo:** https://github.com/rahulvgetmt3/uv-mix-batch (private, branch `main`). `data/`, `Reference/`, `.venv` and the raw chat `.jsonl` are git-ignored.

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
- [ ] **Move the repo** `rahulvgetmt3/uv-mix-batch` to the **MT3-Global-Tech-Inc** org (GitHub › Settings › Transfer ownership).
- [ ] **Rotate the Pulse DB password**, which is exposed and now also on the team test PCs. Create a **read-only** DB user for the portal, then rebuild the team ZIP.
- [ ] **AWS hosting:** an EC2 or Lightsail instance in the DB's region, with a security-group rule to port 3306, a domain such as `uvmix.getmt3.com`, and HTTPS through Caddy. See README › Deploy.
- [ ] **Real logins:** set real `PORTAL_USERS` and a long `SECRET_KEY`, replacing the test `uvteam` login.
- [ ] **Disk:** decide how long to keep runs. A full-bed Spot PDF is about 16 MB per 5 pieces, so expect a few hundred MB for a full bed.

- [ ] **Team history visible to Rahul:** decide on a shared runs folder (OneDrive, Google Drive or network drive) for the testing period. Otherwise it comes automatically with hosting.
- [ ] **Rebuild the team ZIP** (`python3 tools/make_team_zip.py`) before giving it to any new PC. The current TEAM zip predates the UTF-8 fix.

**Known data issues**
- [ ] **B433C9774F** (Mirror 17-P) returned 403 earlier, then downloaded fine later. Watch for other old printcloud `fetch_url`s.

## Sessions

| Dates | Machine | Session | Main topics |
|---|---|---|---|
| 2026-10-11 | Mac | `38c655b4` | HP and Pulse access check; Current Work counts; LUX file download; portal designed and built (scan, bulk, upload, LUX/Mirror batches, File/Die/Spot/Excel, history, login); fixes for full-bed bounding box, right-aligned layout, Spot as a Photoshop-style PDF (Alph block), RIP-safe Die, Reconcile `LUX-15-PL`; GitHub repo; Windows test package; team connected |

The chat is copied to [chat/](chat/). `cleanupPeriodDays` is 3650 in `~/.claude/settings.json`, so the original won't be auto-deleted either.

## Log

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
