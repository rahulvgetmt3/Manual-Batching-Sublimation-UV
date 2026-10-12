---
name: sublimation-rules
description: Sublimation (6UP / 6UP Extended) batching rules from Rahul and how the code implements them (branch 'sublimation')
metadata:
  type: project
---

**Rahul's Sublimation requirements (2026-10-12):** built on git branch **`sublimation`**. `main` stays UV-only until the UV team gets a merged update.

1. **Input:** the same as UV (scan, paste, CSV/XLSX upload).
2. **Two templates.** Both are 318 mm wide with 6 slots, each slot 131.1 mm wide:

   | Template | Sheet height | Slot height |
   |---|---|---|
   | **6UP** | 646 mm | 194.6 mm |
   | **6UP Extended** | 706.5 mm | 214.8 mm |

   The user picks the template per batch. It's pre-set from Pulse: an imposition containing "Extended" → 6UP-EXT.
3. **Sublimation items** are Pulse impositions containing "6up": Casely6up_Bold, Casely-Bold-6up-Extended (+ _AMZ-FBM), Casely6up_Classic, 6up_Sublimation, Casely6up_Sublimation-Extended, Amazon*6up*, Casely6up_MagWallet.
4. **Bold and Classic are never on the same sheet or run**, like LUX and Mirror. The family comes from the **case type** ("BOLD…" → Bold, "CLAS…" → Classic), with the SKU (`-BL-` / `-CL-`) as a fallback. Imposition names mix the two (Classic items sit on Casely-Bold-6up-Extended).
5. **Output:** artwork-only PDFs, **one PDF per sheet** (`SUB_<FAMILY>_<TPL>_<RGB|CMYK>_<date>_NN_S1.pdf`), plus the same Excel (Reconcile model = Pulse model name) and a ZIP. Downloading multiple sheets gives a ZIP of the PDFs.
6. **Placement:**
   - Artwork is at true size (300 DPI), **centred in the slot**.
   - It's **mirrored by default**; a "Flip artwork" toggle allows non-flipped sheets. Mirroring uses the placement matrix only.
   - Slot order is TL, TR, ML, MR, BL, BR.
7. **Names** are `OrderID-Model-CaseType` (for example `#5488010-iPhone 18 Pro-BOLD FLEX - BLUE BUMPER`):
   - left-column pieces on the left edge (baseline x 12.3 mm), right-column pieces on the right edge (x 310.3 mm);
   - 15 pt, reading bottom to top, as black vector outlines (Open Sans, because Myriad isn't available);
   - centred on the slot, but **kept clear of the ⊕ registration marks**, moving into the larger clear stretch and shrinking only if needed.
8. **Colour:**
   - No profile is ever embedded in converted images, and there's no OutputIntent.
   - The **RGB/CMYK export choice applies to the artwork only**: a file already in the chosen mode is untouched, as with UV; otherwise it's converted with the team's **U.S. Web Coated (SWOP) v2** + sRGB, relative colorimetric with BPC.
   - Template marks stay as in the template (CMYK).
9. **QR codes** in the 6UP template held an old SiteFlow barcode (`B61ECAE0B3`) and were **removed**, along with the Extended template's QR placeholders and hidden "MT3-A10…" sample codes.

**Code map:**
- **`tools/build_sub_templates.py`:** re-run it if the team changes the `.ai` files in `Reference/Sublimation/`. It writes to `app/templates/sublimation/`: `6UP.pdf`, `6UP-EXT.pdf`, `templates.json` (slots + mark bands) and `swop.icc`.
- **`app/sub_build.py`:** builds the sheets.
- **`app/runs.py`:** `create_sub_run`.
- **`app/pulse.py`:** `lookup_many(process="sub")`, `sub_template()`, `sub_family()`.
- **UI:** the Manual Batching ▾ dropdown › Sublimation · 6UP › Build batch / History, with per-batch Template, Export and Flip controls.

**Status:** built and tested on Rahul's Mac with real Pulse barcodes (Bold 6UP, Classic 6UP-EXT, RGB/CMYK, flipped and not, 2-sheet runs). **Not yet print-tested by the team or checked in Illustrator/RIP.**

Related: [[uv-mix-portal-overview]], [[pulse-design-system]], [[uv-mix-team-requirements]].
