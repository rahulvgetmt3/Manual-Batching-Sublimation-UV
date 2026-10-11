"""Arrange pieces on the 2180 x 1220 mm UV bed (PDF points, origin bottom-left)."""

from dataclasses import dataclass

MM = 72.0 / 25.4

BED_W = 6181.8   # 2180.8 mm, same as the Illustrator reference
BED_H = 3461.67  # 1221.2 mm
MARGIN = 20 * MM
GAP_X = 7 * MM
GAP_Y = 7 * MM
LABEL_BAND = 10 * MM   # room above each piece for its model label
LABEL_OFFSET = 6 * MM  # label baseline above the piece's top edge


@dataclass
class Placement:
    index: int      # position in the original piece list
    sheet: int      # 1-based
    position: int   # 1-based within the sheet
    x: float
    y: float        # bottom-left corner
    w: float
    h: float


def _order(pieces):
    """Group by label, tallest groups first, so each model sits together."""
    groups = {}
    for i, p in enumerate(pieces):
        groups.setdefault(p["label"], []).append(i)
    keyed = sorted(groups.items(), key=lambda kv: (-max(pieces[i]["h"] for i in kv[1]), kv[0]))
    return [i for _, idxs in keyed for i in idxs]


def layout(pieces):
    """pieces: list of {label, w, h} in points. Returns placements in placement order.

    Right-aligned: rows start at the top-right corner and run right -> left, top -> bottom.
    """
    usable_w = BED_W - 2 * MARGIN
    out = []
    sheet, position = 1, 0
    x = MARGIN
    row_top = BED_H - MARGIN - LABEL_BAND  # top edge of pieces in the current row
    row_h = 0.0

    for i in _order(pieces):
        w, h = pieces[i]["w"], pieces[i]["h"]
        if w > usable_w or h + LABEL_BAND > BED_H - 2 * MARGIN:
            raise ValueError(f"piece {pieces[i]['label']} ({w / MM:.0f} x {h / MM:.0f} mm) is larger than the bed")
        if x + w > MARGIN + usable_w + 0.01:  # next row
            x = MARGIN
            row_top -= row_h + GAP_Y + LABEL_BAND
            row_h = 0.0
        if row_top - h < MARGIN - 0.01:  # next sheet
            sheet += 1
            position = 0
            x = MARGIN
            row_top = BED_H - MARGIN - LABEL_BAND
            row_h = 0.0
        position += 1
        # Start from the right edge: piece 1 sits top-right and each row runs
        # right -> left. Only the position moves; the artwork is never flipped.
        out.append(Placement(i, sheet, position, BED_W - x - w, row_top - h, w, h))
        x += w + GAP_X
        row_h = max(row_h, h)
    return out
