"""
Synthetic GST-compliant invoice payload generator for the spike.

The structure mirrors the IRP schema (Schema-v1.1 envelope: DocDtls, SellerDtls,
BuyerDtls, ValDtls, ItemList, …). Enough of it is filled in for the simulator
and the real sandbox to treat it as valid when we want "clean" submissions,
and a ``with_defect=`` knob injects the common BUSINESS / SCHEMA defects so
the retry + DLQ machinery has something realistic to reject.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import date, datetime, timezone


@dataclass(frozen=True)
class TenantProfile:
    tenant_id: str
    gstin: str
    legal_name: str
    state_code: str


# Five fake tenants mirroring AYY-14's 5-tenant submission profile. GSTIN shape
# follows the public format: 2-digit state, 10-char PAN, entity, Z, checksum.
TENANTS: list[TenantProfile] = [
    TenantProfile("tnt-01", "27ABCDE1234F1Z5", "Mumbai Apparel Co.", "27"),
    TenantProfile("tnt-02", "29ABCDE5678G1Z3", "Bengaluru Threads LLP", "29"),
    TenantProfile("tnt-03", "33ABCDE9012H1Z7", "Chennai Silks Pvt Ltd", "33"),
    TenantProfile("tnt-04", "07ABCDE3456J1Z9", "Delhi Outerwear Pvt Ltd", "07"),
    TenantProfile("tnt-05", "24ABCDE7890K1Z1", "Ahmedabad Textile Co.", "24"),
]


VALID_HSNS = ["6109", "6110", "6204", "6211", "6403", "6505"]


def _invoice_number(tenant: TenantProfile, seq: int, at: datetime) -> str:
    # Fiscal year convention: April–March. Format matches typical Tally docs.
    fy_start = at.year if at.month >= 4 else at.year - 1
    fy = f"{str(fy_start)[-2:]}{str(fy_start + 1)[-2:]}"
    return f"{tenant.tenant_id.upper()}/{fy}/{seq:06d}"


def build_invoice(
    tenant: TenantProfile,
    seq: int,
    at: datetime | None = None,
    rng: random.Random | None = None,
    with_defect: str | None = None,
) -> dict:
    """Return a JSON-serialisable IRP-shaped invoice payload."""
    rng = rng or random.Random(seq ^ hash(tenant.tenant_id))
    at = at or datetime.now(tz=timezone.utc)
    invoice_ref = _invoice_number(tenant, seq, at)

    n_items = rng.randint(1, 6)
    items = []
    taxable_total = 0
    tax_total = 0
    for i in range(n_items):
        unit_price = rng.choice([249, 499, 799, 999, 1499, 1999, 2499])
        qty = rng.randint(1, 4)
        line_taxable = unit_price * qty
        gst_rate = rng.choice([5, 12, 18])
        line_tax = round(line_taxable * gst_rate / 100, 2)
        taxable_total += line_taxable
        tax_total += line_tax
        items.append(
            {
                "SlNo": str(i + 1),
                "PrdDesc": f"SKU-{seq}-{i}",
                "IsServc": "N",
                "HsnCd": rng.choice(VALID_HSNS),
                "Qty": qty,
                "Unit": "NOS",
                "UnitPrice": unit_price,
                "TotAmt": line_taxable,
                "AssAmt": line_taxable,
                "GstRt": gst_rate,
                "IgstAmt": 0,
                "CgstAmt": round(line_tax / 2, 2),
                "SgstAmt": round(line_tax / 2, 2),
                "TotItemVal": line_taxable + line_tax,
            }
        )

    payload = {
        "Version": "1.1",
        "TranDtls": {"TaxSch": "GST", "SupTyp": "B2B", "RegRev": "N"},
        "DocDtls": {
            "Typ": "INV",
            "No": invoice_ref,
            "Dt": at.strftime("%d/%m/%Y"),
        },
        "SellerDtls": {
            "Gstin": tenant.gstin,
            "LglNm": tenant.legal_name,
            "Addr1": "Address line 1",
            "Loc": "City",
            "Pin": 400001,
            "Stcd": tenant.state_code,
        },
        "BuyerDtls": {
            "Gstin": "27AAAPL1234C1Z5",
            "LglNm": "Acme Retail Ltd",
            "Pos": tenant.state_code,
            "Addr1": "Buyer addr 1",
            "Loc": "City",
            "Pin": 400002,
            "Stcd": tenant.state_code,
        },
        "ValDtls": {
            "AssVal": taxable_total,
            "CgstVal": round(tax_total / 2, 2),
            "SgstVal": round(tax_total / 2, 2),
            "IgstVal": 0,
            "TotInvVal": taxable_total + tax_total,
        },
        "ItemList": items,
    }

    # Inject the defects the taxonomy tests care about. Each defect maps to
    # a specific IRP error code class so the tests can assert the right
    # outcome without a fuzzy text match.
    if with_defect == "missing_mandatory":
        # Drop a required envelope field — IRP returns 2100.
        payload.pop("DocDtls", None)
    elif with_defect == "bad_json_shape":
        # Array where an object is required — IRP returns 2119.
        payload["ValDtls"] = [payload["ValDtls"]]
    elif with_defect == "gstin_cancelled_supplier":
        # Marker the simulator recognises; real IRP returns 2211 for a
        # cancelled supplier GSTIN.
        payload["SellerDtls"]["Gstin"] = "00CANCELLED0000"
    elif with_defect == "gstin_cancelled_buyer":
        payload["BuyerDtls"]["Gstin"] = "00CANCELLED0000"
    elif with_defect == "line_math_mismatch":
        # 2182/2189 — totals don't match.
        payload["ValDtls"]["TotInvVal"] = 1
    elif with_defect == "back_dated":
        payload["DocDtls"]["Dt"] = "01/01/2000"
    elif with_defect == "bad_hsn":
        payload["ItemList"][0]["HsnCd"] = "0000"
    elif with_defect == "invalid_pos":
        payload["BuyerDtls"]["Pos"] = "ZZ"
    # Anything else → clean payload.
    return {"invoice_ref": invoice_ref, "payload": payload}


def payload_digest(payload: dict) -> str:
    """Stable hash used as the idempotency key when the source ref isn't."""
    # json.dumps with sort_keys makes the digest order-independent.
    import json

    blob = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()
