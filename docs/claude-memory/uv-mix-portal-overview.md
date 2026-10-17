---
name: uv-mix-portal-overview
description: What the Manual Batching portal (UV Mix + Sublimation) is, current state, branches, and what is still open (as of 2026-10-12)
metadata:
  type: project
---

**What it is:** the MT3 **Manual Batching** portal (FastAPI, `~/Dev/Mix Batch UV and Sublimation/app/`; folder renamed from `Mix Batch UV` on 2026-10-13, GitHub repo `rahulvgetmt3/Manual-Batching-Sublimation-UV`). It replaces the team's manual Illustrator/Photoshop bed builds and is styled exactly like Pulse ([[pulse-design-system]]). The **Manual Batching ▾** menu has two processes:
- **UV Mix (LUX + Mirror):** File PDF, Die PDF (hidden Artwork layer, outlined labels), a Photoshop-style Spot PDF with "Spot Color 1", and Excel. See [[uv-mix-team-requirements]], [[photoshop-spot-channel-psd]] and [[pdf-full-bed-bounding-box]].
- **Sublimation (Bold, Classic, Essential):** artwork-only sheet PDFs (mirrored, centred, names), any-size uploadable templates, CMYK or RGB, and Excel. See [[sublimation-rules]].

**Status, end of 2026-10-12:**
- **2026-10-13:** added Sublimation "Artworks per sheet" (fewer nesting jigs) and rebuilt `dist/Manual-Batching-UPDATE.zip` from `370e51c` for both teams. Open question for Rahul: are the jigs in the top two slots? (Currently the first slots are filled in order.)
- **Latest (all set):** custom artwork on both UV (die at image size, typed name on die) and Sublimation (confirmed working by Rahul). Both teams are updated with `dist/Manual-Batching-UPDATE.zip`, which has no credentials ([[windows-test-package]]). Everything is pushed on branch `sublimation`; `main` has notes only.
- **UV Mix** is on `main`. The UV team tests it on Windows PCs with the local package ([[windows-test-package]]); their PC connects to Pulse. The new Die PDF and Spot PDF have been confirmed in Photoshop but are still pending a printer confirmation.
- **`main`** also has the Pulse theme and the Manual Batching naming, but the UV team's PCs still run the older look until they get an update.
- **Sublimation** is on branch **`sublimation`**, which also has the layout fix (the right column covered the Generate buttons). It's tested on Rahul's Mac with real barcodes, and the **team should test 6UP only** for now. When approved: merge `sublimation` into `main`, then build `app-update.zip` (or the TEAM zip) for both teams.
- **Repo:** https://github.com/rahulvgetmt3/Manual-Batching-Sublimation-UV (renamed from `uv-mix-batch` on 2026-10-13; private, personal account, **testing only**). Later it moves to the **MT3-Global-Tech-Inc** org, with proper hosting (AWS next to the DB, HTTPS, read-only DB user, DB password rotated first). In the end the screens are meant to move **into Pulse** as the "Manual Batching" dropdown.
- **Logins:** Rahul's Mac login is `Rahul` (via `.env` + `./start-mac.sh`); team PCs use `uvteam`. The passwords are in `dist/LOGINS-private.txt` (Mac only).
- **Parked:** the hidden "Rahul admin login on every copy" was blocked as a backdoor and never shipped. The patch is parked in `dist/pending-admin-login.patch` and `dist/pending-admins.json` (Mac only). Options: a disclosed admin login, a shared runs folder, or hosting.

**Why:** the team made mistakes in the manual builds, which took 20–25 minutes per bed.

**How to apply:**
- Treat the team's real print result as the acceptance test.
- Don't put credentials in git.
- New screens should use Pulse classes.
- Keep `main` shippable to the UV team.

Related: [[rahul-profile]], [[pulse-lookup-for-uv-mix]].

**Going live (2026-10-17):** Rahul is moving the portal to a server himself, following README › "Going live on a server" (Docker + Caddy, `/srv/manual-batching-data` volume, 1 uvicorn worker for memory (the MB batch counter uses an OS file lock + atomic replace, so 2 workers are safe on a 16 GB+ host; /data must be a local disk), live counter to start at MB10001 so it doesn't clash with the test PCs). The UV team's test password is now `uvteam123` (fresh package `dist/Manual-Batching-UV-TEAM.zip`); logins are kept in the git-ignored `LOGINS - PRIVATE.txt`. Docker build not tested locally.

**Handover to Pulse devs (2026-10-17):** Rahul wants the devs to merge this into Pulse (React app). Recommended: keep this Python service as the batching engine behind an API, Pulse builds the Manual Batching pages and supplies auth (`_require_user` is the hook), optionally store runs/MB numbers in Pulse DB tables. Written up in `DEVELOPERS.md`. Rahul gives the devs repo access himself.
