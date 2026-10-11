---
name: photoshop-spot-channel-psd
description: How the team's spot file works; spot output is now a Photoshop-style PDF (private PieceInfo data) — PSD was a stopgap
metadata:
  type: reference
---

**How the team's spot file is made:** `Reference/UV_LUX_20261011_01_DIE copy spot.pdf` was saved from Photoshop. The "Spot Color 1" channel equals the **artwork's opacity (alpha), pixel for pixel**. Opaque files get solid spot, transparent PNGs get spot only where pixels are painted, and soft edges get partial ink. The preview colour is white.

**Why it has to be a PSD:**
- Photoshop **flattens any ordinary PDF to RGB on open**, which drops Separation/spot colours. The team's PDF keeps its channel only because of Photoshop's private round-trip data: `/PieceInfo /AdobePhotoshop /Private`, containing CompositeImage, SpotChannels, ImageResources and StandardImageFileData2. That last one is a 62 MB undocumented layer blob with smart objects.
- Cloning that data was rejected as fragile. Rahul chose a **PSD output** (`app/psd_build.py`) instead.

**PSD details that matter:**
- 25757 × 14424 px at 300 ppi, which is 2180.76 × 1221.23 mm, the same as the team's file.
- One RGB layer per piece. The merged composite is written as plain white, the same as Maximize Compatibility off.
- The spot channel is declared through image resources 1006, 1045 and 1007, plus 1077 with kind = 2 (spot).
- **A spot channel's data is stored inverted: 0 = full ink, 255 = none.** I first wrote it non-inverted and Rahul saw the whole bed as spot except the pieces.
- Fast PackBits: Pillow saves a TIFF with `compression="packbits", strip_size=width`, so each strip is one row, and the code reads StripOffsets/StripByteCounts. A full-bed channel encodes in about 0.5 s.

**Validation:** verified with `psd-tools`, and Rahul confirmed in Photoshop that the Spot Color 1 channel appears. Its print behaviour is still pending the team's test.

**Update, 2026-10-11 (later):** Rahul needs the spot file **as a PDF**, not a PSD. `app/spot_pdf.py` now copies the team's Photoshop PDF:
- **Page content:** `/MultiChannelImage` marked content. `Im0` is Indexed over Separation with an inverted LUT (index 0 = full ink), drawn first; `Im1` is RGB with an SMask (Matte 1 1 1, colours premultiplied on white), on top. Both use `/op true`.
- **`/PieceInfo /AdobePhotoshop /Private`:** CompositeImage (the same object as Im1), SpotChannels/XObject/Im1 (the same object as Im0), ImageResources (1005 only, as in the team's file), StandardImageFileData2 and StandardImageFileLength, plus RoundTrip, SaveTransparency and the other flags.
- **StandardImageFileData2 format:** `8BIMLayr` + a u64 length + PSB layer info. Channel lengths are 8 bytes and RLE row counts are 4 bytes. Each layer record has 40 bytes of blending ranges and flags 0x08, and the block is padded to 4 bytes. This was checked against the team's file.
- **Saving:** use `stream_decode_level=StreamDecodeLevel.none`. Otherwise pikepdf writes the pre-deflated images out raw: 1.87 GB instead of 16 MB.

Built in 256-row bands to limit memory. **Not yet confirmed in Photoshop or on the printer.** `psd_build.py` remains only as a helper module (PackBits, piece pixels).
**Photoshop recognition (2026-10-11):** the first spot PDF opened in Photoshop with no spot channel, meaning Photoshop treated it as a generic PDF. The team's file carries Photoshop identification that ours lacked:
- docinfo `/Producer` = "Adobe Photoshop for Windows -- Image Conversion Plug-in";
- an XMP packet with `pdf:Producer`, `photoshop:ColorMode 3` and tiff resolution;
- PDF 1.4 with timezone dates;
- the PieceInfo LastModified about 4 s before the page's.

All of these were added in `spot_pdf.py` (test run `UV_LUX_20261011_24`), and the result is pending Rahul's Photoshop check. **Diagnostic:** if Photoshop shows the "Import PDF" dialog, it still doesn't recognise the file. If it opens directly with layers but no spot channel, the private SpotChannels data is the problem.

**Spot channel definition: the `Alph` block (2026-10-11).** With the Producer and XMP added, Photoshop opened our PDF *as its own*, with layers in the right place, but showed no spot channel. Photoshop defines document spot channels in an **`8BIMAlph` block (8-byte length) at the end of StandardImageFileData2**, after Layr, LMsk and the other blocks. Its layout:
- u32 4, u32 count;
- per channel: u32 record length, then u32 index (3 = after R, G, B) and i32 -1;
- then tagged items: `name` (unicode), `kind` = `8BIMspot`, `opac` = 1 byte (solidity), `colr` (u16 space 1 = HSB, plus 4×u16) and `id  ` (u32).

`spot_pdf._alph_block()` reproduces it byte-for-byte. I also matched the SpotChannels image: CalRGB alternate, lookup as a stream, `/Name /X`, Flate with Predictor 2, and an uncompressed tint function. The test run is `UV_LUX_20261011_26`. **Rahul confirmed it works: Photoshop opens it with Spot Color 1 (2026-10-11).**
