---
name: uv-mix-team-requirements
description: Rahul's confirmed rules for UV mix bed outputs (layout, labels, lines, Excel format) — each was a correction or explicit decision
metadata:
  type: feedback
---

Rules Rahul has set for the UV mix outputs. Each came from a correction or an explicit choice, so don't change one without asking.

- **Only LUX and Mirror.** They print with different methods, so the two lines are **never combined in one PDF or run**. The screen splits them into separate batches.
- **Labels:** the model label (for example `15-PL`) goes **on the Die PDF only, never on the File PDF**. Label text is `batch_imposition` minus the `LUX-` or `MIRROR-` prefix and minus any `_AMZ-FBM` suffix.
- **Artboard** is always the full **2180 × 1220 mm** bed, even when most of it is blank. See [[pdf-full-bed-bounding-box]].
- **Right-aligned:** piece 1 sits in the top-right corner and rows run right to left. **Never flip or mirror the artwork**; only the starting position changes. Rahul pushed back when I used the word "mirror" for this.
- **Die:** the exact bounding box of each file at 300 DPI (no inset), drawn as a 0.75 pt black stroke.
- **Colour:** no colour profile or conversion beyond what the original file already carries. Never convert to CMYK.
- **Files:** use only MT3-approved files (`fetch_url`), never the customer artwork in `hp_od_print_url`.
- **Excel:** the first sheet, "Reconcile", must match the team's tracking sheet. Columns start at A: **A Reconcile (batch number), B Model as line + die label (`LUX-15-PL`, `MIRROR-17-PM`), C Qty.** (Changed from the Pulse model name on 2026-10-11.) Use Calibri 11, centred, bordered, one row per batch + model.
- **Status:** show the exact Pulse job, order and item statuses on screen and in Excel. Only highlight a job that isn't `live` or an order that is `cancelled`/`error`. Reprints legitimately sit on orders that are already `shipped` or `complete`.
- **UI:**
  - Scan, Paste list and Upload file (CSV/XLSX, with downloadable templates) tabs.
  - A History tab at the top.
  - The right panel shows only the last batch, in green.
  - Prominent colour-coded download buttons.

**Why:** these match how the team prints today and how they reconcile batches.

**How to apply:** keep them when changing the layout, PDF or Excel code. See [[uv-mix-portal-overview]].
- **Custom artwork on UV (added 2026-10-12, branch `sublimation`):** same Custom artwork tab as Sublimation (upload/link, table with name + copies). Builds its own `UV_CUSTOM_…` batch: File/Die/Spot + Excel, die = exact image size, the typed name is the die label (shrunk if wider than the piece). Excel Reconcile: batch "CUSTOM", model = typed name. Rahul's ask: "just generate a die based on image size we upload and print name on die as we type in table". See [[sublimation-rules]].
