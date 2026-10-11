"""Spot file as a Photoshop PDF, structured like the team's Photoshop export.

Two parts, both copied from `Reference/UV_LUX_20261011_01_DIE copy spot.pdf`:

1. Printable page (what the RIP reads):
     /MultiChannelImage ... /SpotImage <</Ink (Spot Color 1)>>  -> Im0
     /MainChannelImage                                           -> Im1
   Im0 = full-bed spot channel, Indexed over Separation "Spot Color 1"
         (index 0 = full ink, 255 = none; white preview), drawn first.
   Im1 = full-bed RGB artwork with a soft mask (Matte white), drawn on top.
   Both overprint (ExtGState /op true), exactly like Photoshop writes it.

2. /PieceInfo /AdobePhotoshop /Private (what Photoshop reads to reopen the file
   with layers and the spot channel): CompositeImage, SpotChannels,
   ImageResources and StandardImageFileData2. That last one is the layer data
   in Photoshop's large-document format (8-byte lengths, RLE rows with 4-byte
   counts), with one layer per piece.

Spot ink = artwork opacity. Full where the file is opaque, soft on edges, and
none where a PNG is transparent. Opaque pixels keep their exact RGB values.
Everything is built in horizontal bands, so a full bed never needs the whole
1.1 GB RGB canvas in memory.
"""

import datetime as dt
import struct
import tempfile
import uuid
import zlib

import numpy as np
import pikepdf
from pikepdf import Array, Dictionary, Name

from .layout import BED_H
from .psd_build import DOC_H, DOC_W, PPI, SPOT_NAME, _packbits_rows, _piece_pixels, _resource

BAND = 256  # rows per band
PAGE_W = DOC_W / PPI * 72  # 6181.68 pt
PAGE_H = DOC_H / PPI * 72  # 3461.76 pt


# Photoshop only treats a PDF as its own round-trip file (and reads the private
# layer/spot data) when the Producer and XMP identify it as a Photoshop PDF;
# otherwise it opens it as a generic PDF and flattens it to RGB.
PS_PRODUCER = "Adobe Photoshop for Windows -- Image Conversion Plug-in"


def _pdf_date(t):
    off = t.strftime("%z")  # +0530 -> +05'30'
    return t.strftime("D:%Y%m%d%H%M%S") + (f"{off[:3]}'{off[3:]}'" if off else "")


def _xmp(title, t):
    iso = t.isoformat(timespec="seconds")
    doc = f"xmp.did:{uuid.uuid4()}"
    return f"""<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"
    xmlns:pdf="http://ns.adobe.com/pdf/1.3/"
    xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/"
    xmlns:tiff="http://ns.adobe.com/tiff/1.0/"
    xmlns:exif="http://ns.adobe.com/exif/1.0/">
   <dc:format>application/pdf</dc:format>
   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{title}</rdf:li></rdf:Alt></dc:title>
   <xmp:CreatorTool>MT3 UV Mix Batch</xmp:CreatorTool>
   <xmp:CreateDate>{iso}</xmp:CreateDate>
   <xmp:ModifyDate>{iso}</xmp:ModifyDate>
   <xmp:MetadataDate>{iso}</xmp:MetadataDate>
   <xmpMM:DocumentID>{doc}</xmpMM:DocumentID>
   <xmpMM:InstanceID>uuid:{uuid.uuid4()}</xmpMM:InstanceID>
   <xmpMM:OriginalDocumentID>{doc}</xmpMM:OriginalDocumentID>
   <pdf:Producer>{PS_PRODUCER}</pdf:Producer>
   <photoshop:ColorMode>3</photoshop:ColorMode>
   <tiff:Orientation>1</tiff:Orientation>
   <tiff:XResolution>3000000/10000</tiff:XResolution>
   <tiff:YResolution>3000000/10000</tiff:YResolution>
   <tiff:ResolutionUnit>2</tiff:ResolutionUnit>
   <tiff:ImageWidth>{DOC_W}</tiff:ImageWidth>
   <tiff:ImageLength>{DOC_H}</tiff:ImageLength>
   <exif:PixelXDimension>{DOC_W}</exif:PixelXDimension>
   <exif:PixelYDimension>{DOC_H}</exif:PixelYDimension>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""


def _boxes(placements):
    """Pixel box (top, left, h, w) for each placement on the 300 ppi canvas."""
    out = []
    for p in placements:
        w = round(p.w / 72 * PPI)
        h = round(p.h / 72 * PPI)
        left = min(max(round(p.x / 72 * PPI), 0), DOC_W - w)
        top = min(max(round((BED_H - (p.y + p.h)) / 72 * PPI), 0), DOC_H - h)
        out.append((top, left, h, w))
    return out


class _Deflater:
    """Collects zlib-compressed output chunk by chunk."""

    def __init__(self, level=6):
        self.z, self.parts = zlib.compressobj(level), []

    def add(self, b):
        self.parts.append(self.z.compress(b))

    def done(self):
        self.parts.append(self.z.flush())
        return b"".join(self.parts)


def _spot_colorspace(pdf):
    """Indexed over Separation 'Spot Color 1', exactly as Photoshop writes it:
    CalRGB (sRGB) alternate, white preview, inverted lookup stream
    (index i -> tint (255 - i) / 255)."""
    fn = pikepdf.Stream(pdf, b"{dup dup 0.000000 mul 1.0 add 3 1 roll 0.000000 mul 1.0 add "
                             b"3 1 roll 0.000000 mul 1.0 add 3 1 roll}")
    fn.FunctionType, fn.Domain, fn.Range = 4, Array([0.0, 1.0]), Array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    calrgb = Array([Name.CalRGB, Dictionary(
        BlackPoint=Array([0.0, 0.0, 0.0]),
        Gamma=Array([2.2, 2.2, 2.2]),
        Matrix=Array([0.412384, 0.212631, 0.0193329, 0.35759, 0.715164, 0.119186, 0.180481, 0.0721893, 0.950516]),
        WhitePoint=Array([0.950455, 1.0, 1.08905]),
    )])
    sep = Array([Name.Separation, Name("/" + SPOT_NAME), calrgb, pdf.make_indirect(fn)])
    lut = pdf.make_indirect(pikepdf.Stream(pdf, bytes(range(255, -1, -1))))
    return pdf.make_indirect(Array([Name.Indexed, sep, 255, lut]))


def _predict(band):
    """TIFF predictor 2 (horizontal differencing), as Photoshop uses for these images."""
    out = band.copy()
    if band.ndim == 2:
        out[:, 1:] = band[:, 1:] - band[:, :-1]
    else:
        out[:, 1:, :] = band[:, 1:, :] - band[:, :-1, :]
    return out


def _image(pdf, data, w, h, cs, colors, **extra):
    xo = pikepdf.Stream(pdf, b"")
    parms = Dictionary(BitsPerComponent=8, Colors=colors, Columns=w, Predictor=2)
    xo.write(data, filter=Name.FlateDecode, decode_parms=parms)
    xo.Name = Name.X
    xo.Type, xo.Subtype = Name.XObject, Name.Image
    xo.Width, xo.Height, xo.BitsPerComponent, xo.ColorSpace = w, h, 8, cs
    for k, v in extra.items():
        xo[Name("/" + k)] = v
    return pdf.make_indirect(xo)


def _canvases(placements, pieces):
    """Band-by-band: composite RGB (Matte white), alpha, and spot index streams,
    plus the per-piece layer channel data written to a temp file."""
    boxes = _boxes(placements)
    rgb_z, a_z, s_z = _Deflater(), _Deflater(), _Deflater()
    cache = {}  # placement idx -> (rgb, alpha) while its rows are in play
    for y0 in range(0, DOC_H, BAND):
        y1 = min(y0 + BAND, DOC_H)
        rgb = np.full((y1 - y0, DOC_W, 3), 255, np.uint8)
        alpha = np.zeros((y1 - y0, DOC_W), np.uint8)
        for i, (top, left, h, w) in enumerate(boxes):
            if top + h <= y0:  # piece finished above this band
                cache.pop(i, None)
                continue
            if top >= y1:  # piece starts below this band
                continue
            if i not in cache:
                cache[i] = _piece_pixels(pieces[placements[i].index]["path"], w, h)
            prgb, pa = cache[i]
            a, b = max(y0, top), min(y1, top + h)
            src_rgb, src_a = prgb[a - top:b - top], pa[a - top:b - top]
            # premultiply against white (Matte [1 1 1]); opaque pixels unchanged
            af = src_a[..., None].astype(np.uint16)
            comp = ((src_rgb.astype(np.uint16) * af + 255 * (255 - af) + 127) // 255).astype(np.uint8)
            rgb[a - y0:b - y0, left:left + w] = comp
            alpha[a - y0:b - y0, left:left + w] = src_a
        rgb_z.add(_predict(rgb).tobytes())
        a_z.add(_predict(alpha).tobytes())
        s_z.add(_predict(255 - alpha).tobytes())  # spot index: 0 = full ink
    return rgb_z.done(), a_z.done(), s_z.done()


def _alph_block():
    """'Alph' block: Photoshop's definition of the document spot channel
    (name, kind = spot, solidity, colour, id), byte-for-byte in the team's layout.
    Without it Photoshop loads the layers but creates no spot channel."""
    name_u = SPOT_NAME.encode("utf-16-be")
    items = [
        (b"name", struct.pack(">I", len(SPOT_NAME)) + name_u),
        (b"kind", b"8BIMspot"),
        (b"opac", b"\x00"),                                        # solidity 0 %
        (b"colr", struct.pack(">H4H", 1, 0, 0, 0xFFFF, 0)),        # HSB white preview
        (b"id  ", struct.pack(">I", 7)),
    ]
    rec = struct.pack(">Ii", 3, -1)                                 # channel index 3 (after R, G, B)
    for key, data in items:
        rec += b"8BIM" + key + struct.pack(">I", len(data)) + data + b"\0" * (-len(data) % 4)
    body = struct.pack(">II", 4, 1) + struct.pack(">I", len(rec)) + rec
    return b"8BIMAlph" + struct.pack(">Q", len(body)) + body


def _layer_data(placements, pieces, items):
    """StandardImageFileData2: '8BIMLayr' + u64 length + PSB layer info, deflated.

    Returns (deflated bytes, decoded length)."""
    boxes = _boxes(placements)
    recs = [struct.pack(">h", len(placements))]
    blends = struct.pack(">10I", *([0x0000FFFF] * 10))
    with tempfile.TemporaryFile() as tmp:
        for p, (top, left, h, w) in zip(placements, boxes):
            prgb, pa = _piece_pixels(pieces[p.index]["path"], w, h)
            r = struct.pack(">iiiiH", top, left, top + h, left + w, 4)
            for cid, arr in ((-1, pa), (0, prgb[:, :, 0]), (1, prgb[:, :, 1]), (2, prgb[:, :, 2])):
                counts, data = _packbits_rows(arr)
                blob = struct.pack(">H", 1) + struct.pack(f">{len(counts)}I", *counts) + data
                r += struct.pack(">hQ", cid, len(blob))
                tmp.write(blob)
            it = items[p.index]
            name = f"{p.position:03d} {it.label} {it.component_barcode}".encode("latin-1", "replace")[:255]
            pname = bytes([len(name)]) + name
            pname += b"\0" * (-len(pname) % 4)
            extra = struct.pack(">I", 0) + struct.pack(">I", len(blends)) + blends + pname
            recs.append(r + b"8BIMnorm" + struct.pack(">BBBB", 255, 0, 0x08, 0)
                        + struct.pack(">I", len(extra)) + extra)
        head = b"".join(recs)
        info_len = len(head) + tmp.tell()
        pad = -info_len % 4
        z = _Deflater()
        z.add(b"8BIMLayr" + struct.pack(">Q", info_len) + head)
        tmp.seek(0)
        while chunk := tmp.read(1 << 24):
            z.add(chunk)
        z.add(b"\0" * pad)
        alph = _alph_block()
        z.add(alph)
        return z.done(), 16 + info_len + pad + len(alph)


def build_spot_pdf(placements, pieces, items, out_path, title):
    """Write one Photoshop-style spot PDF for one sheet's placements."""
    pdf = pikepdf.new()
    t = dt.datetime.now().astimezone().replace(microsecond=0)
    now = pikepdf.String(_pdf_date(t))
    piece_time = pikepdf.String(_pdf_date(t - dt.timedelta(seconds=4)))  # as Photoshop: private data saved just before the page
    pdf.docinfo[Name.Title] = title
    pdf.docinfo[Name.Creator] = "MT3 UV Mix Batch"
    pdf.docinfo[Name.Producer] = PS_PRODUCER
    pdf.docinfo[Name.CreationDate] = now
    pdf.docinfo[Name.ModDate] = now
    meta = pikepdf.Stream(pdf, _xmp(title, t).encode("utf-8"))
    meta.Type, meta.Subtype = Name.Metadata, Name.XML
    pdf.Root.Metadata = pdf.make_indirect(meta)

    rgb_data, a_data, s_data = _canvases(placements, pieces)
    cs = _spot_colorspace(pdf)
    smask = _image(pdf, a_data, DOC_W, DOC_H, Name.DeviceGray, 1, Matte=Array([1, 1, 1]))
    im_rgb = _image(pdf, rgb_data, DOC_W, DOC_H, Name.DeviceRGB, 3, SMask=smask)
    im_spot = _image(pdf, s_data, DOC_W, DOC_H, cs, 1)

    layers, layers_len = _layer_data(placements, pieces, items)
    layer_stream = pikepdf.Stream(pdf, b"")
    layer_stream.write(layers, filter=Name.FlateDecode)

    res_blob = _resource(1005, struct.pack(">IHHIHH", PPI << 16, 1, 2, PPI << 16, 1, 2))
    img_res = pikepdf.Stream(pdf, res_blob)

    private = Dictionary(
        CompositeImage=im_rgb,
        SpotChannels=Dictionary(N=1, XObject=Dictionary(Im1=im_spot)),
        ImageResources=pdf.make_indirect(img_res),
        StandardImageFileData2=pdf.make_indirect(layer_stream),
        StandardImageFileLength=layers_len,
        RoundTrip=True, SaveTransparency=True, EmbedFonts=True, ExportCrispy=True, UseTextOutlines=False,
    )

    ink = b"\xfe\xff" + SPOT_NAME.encode("utf-16-be") + b"\x00\x00"  # as Photoshop writes it
    ink_lit = ink.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    ops = (b"/MultiChannelImage <</MainChannel /RGBColorMode /Spot [(" + ink_lit + b")]>>BDC \n"
           b"/SeparationImages BMC \n"
           b"/SpotImage <</Ink (" + ink_lit + b")>>BDC \n"
           + f"q\n/GS0 gs\n/RelativeColorimetric ri\n{PAGE_W:.7f} 0 0 {PAGE_H:.7f} 0 0 cm\n/Im0 Do\nQ\nEMC \n".encode()
           + b"/MainChannelImage BMC \n"
           + f"q\n/GS0 gs\n/RelativeColorimetric ri\n{PAGE_W:.7f} 0 0 {PAGE_H:.7f} 0 0 cm\n/Im1 Do\nQ\nEMC \n".encode()
           + b"EMC \nEMC \n")

    box = Array([0, 0, PAGE_W, PAGE_H])
    page = pikepdf.Page(Dictionary(
        Type=Name.Page, MediaBox=box, CropBox=box, ArtBox=box, Rotate=0, LastModified=now,
        Contents=pdf.make_stream(ops),
        Resources=Dictionary(
            XObject=Dictionary(Im0=im_spot, Im1=im_rgb),
            ColorSpace=Dictionary(CS0=cs),
            ExtGState=Dictionary(GS0=Dictionary(Type=Name.ExtGState, op=True)),
            ProcSet=Array([Name.PDF, Name.ImageC, Name.ImageI]),
        ),
        PieceInfo=Dictionary(AdobePhotoshop=Dictionary(LastModified=piece_time, Private=private)),
    ))
    pdf.pages.append(page)
    # keep our pre-deflated streams as they are (do not decode and rewrite them)
    pdf.save(out_path, min_version="1.4", compress_streams=False,
             stream_decode_level=pikepdf.StreamDecodeLevel.none)
