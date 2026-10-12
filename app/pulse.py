"""Read-only lookups against Pulse (mt3narada) by component (or item) barcode."""

import os
import re
from dataclasses import dataclass, asdict

import mysql.connector

# Product lines this tool handles, keyed by batch_imposition prefix.
# Each line prints with a different method, so a run never mixes them.
LINES = {"LUX": "LUX", "MIRROR": "MIRROR"}

BARCODE_RE = re.compile(r"^[A-Z0-9]{6,20}$")

QUERY = """
SELECT i.component_barcode, i.item_barcode, i.fetch_url, i.sku, i.model, i.case_type,
       i.batch_imposition, i.hp_od_code, i.hp_od_print_sku, i.item_status,
       o.order_id AS hp_order_id, o.source_id AS order_number, o.source, o.order_status,
       j.id AS job_row, j.full_batch_number, j.status AS job_status, j.reprint, j.reprint_reason,
       j.hp_updated_at AS status_updated
FROM hp_order_items i
JOIN hp_orders o ON o.id = i.hp_order_id
LEFT JOIN hp_jobs j ON j.barcode = i.component_barcode
WHERE i.component_barcode IN ({ph}) OR i.item_barcode IN ({ph})
"""


class LookupError_(Exception):
    """A scan that must be rejected; message is shown to the operator."""


@dataclass
class Item:
    component_barcode: str
    item_barcode: str
    fetch_url: str
    sku: str
    model: str
    case_type: str
    batch_imposition: str
    print_code: str
    print_sku: str
    hp_order_id: str
    order_number: str
    source: str
    batch_number: str
    job_status: str
    order_status: str
    item_status: str
    reprint: bool
    reprint_reason: str
    status_updated: str
    line: str
    label: str
    reconcile_model: str = ""
    family: str = ""

    def to_dict(self):
        return asdict(self)


def _connect():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "pulse.getmt3.com"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ.get("DB_NAME", "mt3narada"),
        connection_timeout=20,
    )


def line_and_label(batch_imposition):
    """'LUX-15-PL' -> ('LUX', '15-PL'); 'MIRROR-17_AMZ-FBM' -> ('MIRROR', '17')."""
    imp = (batch_imposition or "").strip()
    prefix, _, rest = imp.partition("-")
    line = LINES.get(prefix.upper())
    if not line or not rest:
        return None, None
    return line, re.sub(r"_AMZ-FBM$", "", rest, flags=re.I)


def is_sublimation(family, batch_imposition):
    """All Bold, Classic and Essential items are sublimation, whatever the model or imposition
    (e.g. 'Casely-Bold-13/14/15', 'Casely-Bold-16e/17e'), plus anything on a 6up / Sublimation
    imposition (Rahul, 2026-10-12)."""
    imp = (batch_imposition or "").lower()
    return family in ("BOLD", "CLASSIC", "ESSENTIAL") or "6up" in imp or "sublimation" in imp


def sub_template(batch_imposition):
    """Sublimation items are the 6UP impositions ('Casely6up_Bold', 'Casely-Bold-6up-Extended',
    '6up_Sublimation', ...). Suggested template: 6UP Extended if the name says Extended, else 6UP."""
    imp = (batch_imposition or "").lower()
    if "6up" not in imp:
        return None
    return "6UP-EXT" if "extended" in imp else "6UP"


# Products that are never sublimated (UV / other processes). Blocked on the Sublimation page even if
# Pulse ever puts them on a 6UP imposition (Rahul, 2026-10-12).
_SUB_BLOCK_SKU = {"LX", "MR", "IPD", "LP", "KND", "MB", "MAC"}   # LUX, Mirror, iPad, Laptop, Kindle, MacBook
_SUB_BLOCK_WORDS = ("LUX", "ALIGN", "MIRROR", "IPAD", "LAPTOP", "MACBOOK", "KINDLE")


def sub_blocked(sku, case_type, batch_imposition):
    """Name of the blocked product if this item must not go on a Sublimation sheet, else None."""
    segs = set((sku or "").upper().replace("_", "-").split("-"))
    hit = segs & _SUB_BLOCK_SKU
    if hit:
        return {"LX": "LUX", "MR": "Mirror", "IPD": "iPad", "LP": "Laptop", "KND": "Kindle",
                "MB": "MacBook", "MAC": "MacBook"}[sorted(hit)[0]]
    text = f"{case_type or ''} {batch_imposition or ''}".upper()
    for w in _SUB_BLOCK_WORDS:
        if w in text:
            return {"ALIGN": "LUX"}.get(w, w.title())
    return None


def sub_family(case_type, sku=""):
    """Bold and Classic print on separate sheets. Family comes from the case type
    ('BOLD FLEX - BLACK BUMPER', 'BOLD - BLACK' = Bold; 'CLAS-BK', 'CLAS-CL' = Classic), with the SKU
    as a fallback (CS-BL- = Bold, CS-CL-/AM-CL- = Classic). Imposition names mix them, so they are not used."""
    ct = (case_type or "").upper()
    if "BOLD" in ct:
        return "BOLD"
    if "CLAS" in ct:
        return "CLASSIC"
    if "TOUGH" in ct or "SLIM" in ct:   # Essential case types (Tough / Slim, with or without MagSafe)
        return "ESSENTIAL"
    # SKU fallback: product code right after the brand prefix only (CS-BL-, AM-CL-, CS-FBM-ES-, ES-...),
    # so e.g. clear generic cases 'CS-GC-IP12-CL-MG' (CL = clear colour) are not taken for Classic.
    m = re.match(r"^(?:(?:CS|AM)-)?(?:FBM-)?(BL|CL|ES)-", (sku or "").upper())
    if m:
        return {"BL": "BOLD", "CL": "CLASSIC", "ES": "ESSENTIAL"}[m.group(1)]
    return "OTHER"


def normalise(codes):
    """Uppercase, strip, de-duplicate (keeping order)."""
    return list(dict.fromkeys(c.strip().upper() for c in codes if c and c.strip()))


def _to_item(row, process="uv"):
    code = row["component_barcode"]
    if process == "sub":
        blocked = sub_blocked(row["sku"], row["case_type"], row["batch_imposition"])
        if blocked:
            raise LookupError_(f"{code}: {blocked} is not printed by sublimation ({row['sku']})")
        family = sub_family(row["case_type"], row["sku"])
        if not is_sublimation(family, row["batch_imposition"]):
            raise LookupError_(f"{code}: {row['batch_imposition'] or row['sku']} is not a Sublimation item")
        line = sub_template(row["batch_imposition"]) or "6UP-EXT"
        # side name on the sheet: OrderID-Model-CaseType, e.g. "#4848818-iPhone 17 Pro-BOLD FLEX - BLACK BUMPER"
        label = f"{row['order_number'] or ''}-{row['model'] or ''}-{row['case_type'] or ''}"
        reconcile = row["model"] or ""
    else:
        line, label = line_and_label(row["batch_imposition"])
        if not line:
            raise LookupError_(f"{code}: {row['batch_imposition'] or row['sku']} is not LUX or Mirror")
        reconcile = f"{line}-{label}"
        family = line
    if not row["fetch_url"]:
        raise LookupError_(f"{code}: no MT3 print file (fetch_url) in Pulse")
    return Item(
        component_barcode=code,
        item_barcode=row["item_barcode"] or "",
        fetch_url=row["fetch_url"],
        sku=row["sku"] or "",
        model=row["model"] or "",
        case_type=row["case_type"] or "",
        batch_imposition=row["batch_imposition"],
        print_code=row["hp_od_code"] or "",
        print_sku=row["hp_od_print_sku"] or "",
        hp_order_id=row["hp_order_id"] or "",
        order_number=row["order_number"] or "",
        source=row["source"] or "",
        batch_number=(row["full_batch_number"] or "").split(" /")[0],
        job_status=row["job_status"] or "no job",
        order_status=row["order_status"] or "",
        item_status=row["item_status"] or "",
        reprint=bool(row["reprint"]),
        reprint_reason=row["reprint_reason"] or "",
        status_updated=row["status_updated"].strftime("%Y-%m-%d %H:%M") if row["status_updated"] else "",
        line=line,
        label=label,
        reconcile_model=reconcile,
        family=family,
    )


def lookup_many(codes, process="uv"):
    """Look up component or item barcodes in one pass. process: 'uv' (LUX/Mirror) or 'sub' (6UP).

    Returns (items, errors): items keyed by the code as given, errors as {code: message}.
    """
    codes = normalise(codes)
    items, errors = {}, {}
    valid = []
    for c in codes:
        (valid.append(c) if BARCODE_RE.match(c) else errors.__setitem__(c, f"'{c}' is not a valid barcode"))

    rows = []
    if valid:
        conn = _connect()
        try:
            cur = conn.cursor(dictionary=True)
            for i in range(0, len(valid), 500):
                chunk = valid[i:i + 500]
                ph = ",".join(["%s"] * len(chunk))
                cur.execute(QUERY.format(ph=ph), chunk + chunk)
                rows += cur.fetchall()
        finally:
            conn.close()

    # Latest hp_jobs row wins: reprints create new jobs for the same barcode.
    best = {}
    for r in rows:
        for key in (r["component_barcode"], r["item_barcode"]):
            if key and (key not in best or (r["job_row"] or 0) > (best[key]["job_row"] or 0)):
                best[key] = r

    for c in valid:
        r = best.get(c)
        if not r:
            errors[c] = f"{c}: not found in Pulse"
            continue
        try:
            items[c] = _to_item(r, process)
        except LookupError_ as e:
            errors[c] = str(e)
    return items, errors


def lookup_component(barcode, process="uv"):
    items, errors = lookup_many([barcode], process)
    code = normalise([barcode])[0] if barcode.strip() else ""
    if code in items:
        return items[code]
    raise LookupError_(errors.get(code, f"'{barcode}' is not a valid barcode"))
