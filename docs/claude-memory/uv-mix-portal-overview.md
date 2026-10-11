---
name: uv-mix-portal-overview
description: What the UV Mix Batch portal is, its current state, and what is still open (as of 2026-10-11 end of day)
metadata:
  type: project
---

The UV Mix Batch portal replaces the team's manual Illustrator/Photoshop bed builds for **LUX and Mirror** phone cases. That manual process took 20–25 minutes per bed and was error-prone. It is a FastAPI app in `~/Dev/Mix Batch UV/app/`.

**Flow:** the operator scans, pastes or uploads component barcodes (B433…). The app looks each one up in Pulse (`mt3narada`) and downloads the MT3-approved `fetch_url` file. It then outputs, for a 2180 × 1220 mm bed:
- **File PDF**;
- **Die PDF**, with a hidden Artwork layer and outlined labels;
- **Spot PDF**, a Photoshop-style PDF with a "Spot Color 1" channel;
- **Excel**, with a Reconcile sheet.

These come as a ZIP, and runs are kept in a history.

**Status at end of 2026-10-11:**
- **Confirmed by Rahul:**
  - the Spot PDF opens in Photoshop with Spot Color 1;
  - layouts are right-aligned on the full bed;
  - the Reconcile sheet uses the `LUX-15-PL` model format.
- **Team testing:** the team tests on Windows PCs with the local package (`Setup.bat` / `Start UV Mix.bat`). Rahul built the pre-filled team ZIP, and the **team PC connected to Pulse**.
- **Still to confirm on the printer:** the new Die PDF (PDF 1.6, hidden Artwork layer, outlined labels) and the Spot PDF.
- **Code:** at https://github.com/rahulvgetmt3/uv-mix-batch (private, Rahul's personal account, **testing only**). Plan: once testing passes, move it to the **MT3-Global-Tech-Inc** org and host it properly. Hosting is AWS next to the DB, with HTTPS, team logins, a read-only DB user, and the DB password rotated first.

**Why:** the team had made mistakes in the manual build, and Rahul wants an online portal the team can use.

**How to apply:**
- Treat the team's real print result as the acceptance test. Their reference files are in `Reference/`.
- Don't put credentials in git.

Related: [[uv-mix-team-requirements]], [[photoshop-spot-channel-psd]], [[pdf-full-bed-bounding-box]], [[pulse-lookup-for-uv-mix]], [[windows-test-package]].
