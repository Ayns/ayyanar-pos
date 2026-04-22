"""
AYY-34 — Shared utilities.
"""

from decimal import Decimal

# ── Currency helpers ──
def paise_to_rupees(paise):
    """Convert paise (int) to Decimal rupees."""
    return Decimal(paise) / 100

def rupees_to_paise(rupees):
    """Convert Decimal/float rupees to int paise."""
    if isinstance(rupees, float):
        return int(round(rupees * 100))
    return int(Decimal(str(rupees)) * 100)

# ── GST helpers ──
def compute_gst_amount(taxable_value_paise, gst_slab, is_inter_state):
    """Compute CGST/SGST or IGST from taxable value in paise."""
    rate = Decimal(str(gst_slab))
    taxable = Decimal(str(taxable_value_paise))
    total_tax = (taxable * rate / Decimal("100")).quantize(Decimal("1"))

    if is_inter_state:
        return 0, 0, int(total_tax)
    else:
        half = total_tax // 2
        return int(half), int(total_tax - half), 0

# ── Barcode helpers ──
def generate_ean13(uuid_int):
    """Generate EAN-13 check digit from integer."""
    raw = str(uuid_int)[:12].zfill(12)
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(raw))
    check = (10 - (total % 10)) % 10
    return raw + str(check)

# ── Barcode label formatting ──
def format_label_text(style_code, style_name, colour, size, mrp_paise, hsn, label_size="50x25"):
    """Format text for barcode label printing."""
    mrp = Decimal(mrp_paise) / 100
    lines = []
    if label_size == "50x25":
        lines.extend([
            style_name,
            f"{colour} | {size}",
            f"Rs {mrp}",
            hsn,
        ])
    else:
        lines.extend([
            f"{style_code} {size}",
            f"Rs {mrp}",
        ])
    return "\n".join(lines)
