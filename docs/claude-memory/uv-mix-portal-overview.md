---
name: uv-mix-portal-overview
description: What the UV Mix Batch portal is, its current state, and what is still open (as of 2026-10-11)
metadata:
  type: project
---

The UV Mix Batch portal replaces the team's manual Illustrator/Photoshop bed builds for **LUX and Mirror** phone cases. That manual process took 20–25 minutes per bed and was error-prone. It is a FastAPI app in `~/Dev/Mix Batch UV/app/`.

**Flow:** the operator scans, pastes or uploads component barcodes (B433…). The app looks each one up in Pulse (`mt3narada`) and downloads the MT3-approved `fetch_url` file. It then outputs File PDF + Die PDF + Spot PSD + Excel for a 2180 × 1220 mm bed, as a ZIP, and keeps a run history.

**Status on 2026-10-11:**
- Built and tested locally on Rahul's Mac, at `localhost:8765` with login `test` / `test123`.
- The team is about to do a real print test of the File, Die and Spot outputs, including multiple batches.
- **Not deployed yet.** The chosen hosting is a cloud server (AWS, next to the DB), with a login and ZIP downloads. Deploying needs AWS access, a domain, a read-only DB user, and the DB password rotated first.

**Why:** the team had made mistakes in the manual build, and Rahul wants an online portal the team can use.

**How to apply:** treat the team's real print result as the acceptance test. Their reference files are in `Reference/`. Related: [[uv-mix-team-requirements]], [[photoshop-spot-channel-psd]], [[pdf-full-bed-bounding-box]], [[pulse-lookup-for-uv-mix]].
