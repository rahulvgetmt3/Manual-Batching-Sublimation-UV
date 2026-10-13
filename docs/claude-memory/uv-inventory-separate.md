---
name: uv-inventory-separate
description: UV Inventory is NOT in this repo; it lives in ~/Dev/UV Inventory Model (own git). This folder is only UV + Sublimation batching
metadata:
  type: feedback
---

This folder (`~/Dev/Mix Batch UV`) is **only for UV and Sublimation batching**. UV Inventory (stock of printed UV cases in bins, port 8766) was built here by mistake on 2026-10-13. The same day it was moved to **`~/Dev/UV Inventory Model`**, which has its own git, `.env`, data and memory. All inventory files, data and branches were removed from here.

**Why:** Rahul wants each module in its own folder and repo; he thought the inventory work was already happening in the other folder.

**How to apply:**
- Any inventory request goes to `~/Dev/UV Inventory Model`, never to this repo.
- Check which folder you're in before editing.
