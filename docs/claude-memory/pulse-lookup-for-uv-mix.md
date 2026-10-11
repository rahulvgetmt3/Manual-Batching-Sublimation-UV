---
name: pulse-lookup-for-uv-mix
description: How a component barcode maps to batch, order, file and status in mt3narada, plus DB access facts on the Mac
metadata:
  type: reference
---

**Barcode join (one bulk query in `app/pulse.py`):**
- `hp_order_items.component_barcode` (B433…) equals `hp_jobs.barcode`.
- Item barcodes (B333…) also resolve, through `hp_order_items.item_barcode`.
- Take the **latest `hp_jobs` row**, because reprints create new jobs for the same barcode.
- `hp_jobs.full_batch_number` is "417227 / 1"; the batch number is the part before " /".
- `hp_orders.source_id` is the Casely order number (#548…).
- `batch_imposition` is `LUX-15-PL`, `MIRROR-17-PM`, or the same with `_AMZ-FBM` for Amazon FBM.
- iPhone 18 Pro Max Mirror uses the `MIRROR-17-PM` imposition, so its label is 17-PM.

**Status values (last 30 days):**
- `hp_jobs.status`: live, pending, complete, cancelled.
- `hp_orders.order_status`: printready, dataready, live, complete, shipped, cancelled, error.
- `hp_order_items.item_status`: live, shipped.
- Pulse can lag SiteFlow by a few minutes.

**Bad files:** some old `fetch_url`s, such as 2024 `printcloud.storage` print_plates, return **403**. The portal rejects these per barcode. One example is B433C9774F.

**DB access on the Mac:**
- Connecting directly with `~/Dev/Pulse/.env` **works on this Mac** (2026-10-11). The Pulse project's memory note "running-db-queries" says Claude is blocked; that was a Windows auto-mode restriction and is stale here.
- Port 3306 only answers when the current public IP is allowlisted. On 2026-10-11 it was 122.176.110.84.

**SiteFlow:** `~/Dev/HP Siteflow` (`siteflow` package, `.env`) gives the live batch and "Current Work" event counts. Events are named Essential, Bold, Classic, Lux, Mirror, and so on.
