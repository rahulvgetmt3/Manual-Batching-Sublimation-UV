---
name: pdf-full-bed-bounding-box
description: Photoshop crops PDFs to the artwork bounding box; the team's Illustrator files use an invisible full-page frame to force 2180x1220
metadata:
  type: reference
---

**Problem:** Photoshop opens a PDF with "Crop To: Bounding Box". So a PDF whose page is 2180 × 1221 mm but whose pieces fill only one corner opened at about 465 × 183 mm. Rahul flagged this as "overall boundary box size is small".

**How the team's files avoid it:** their Illustrator PDFs (`Reference/LUX MIX FILE.pdf` and `LUX MIX DIE.pdf`) contain Form XObject `Fm0`. It's a 0.75 pt black stroke round the whole artboard with ExtGState `CA 0 / ca 0` (0% opacity), wrapped in a transparency group. It prints nothing, but it makes the bounding box the full bed.

**Our fix:** `app/pdf_build.py` `_frame()` adds the same invisible frame to every page of the File and Die PDFs.

The page size is 6181.8 × 3461.67 pt (2180.8 × 1221.2 mm), matching the reference. The PSD spot file doesn't need the frame, because its canvas is the full bed.

Related: [[uv-mix-team-requirements]].

**RIP compatibility (2026-10-11):** the printer could not take our first Die PDF, which was 2 KB. The differences from the team's die were:
- PDF 1.3 while using transparency, which needs PDF 1.4 or later;
- a non-embedded Helvetica font;
- missing CropBox, BleedBox and ArtBox;
- no hidden artwork layer.

Now both PDFs are PDF 1.6 with all boxes set. Die labels are glyph outlines made with fontTools from the bundled `app/fonts/OpenSans-Regular.ttf`. The Die PDF has an OCG "Artwork" layer (off) and a "Die" layer (on), mirroring the team's Layer 1 and Layer 2. Whether this fixed the printer was still to be confirmed.
