"""
CSV import for product catalogue seeding — AYY-29 v0.1.

Accepts a CSV with columns:
  sku, style, color, size, mrp_paise, cost_price_paise, season_tag, hsn_code

One row per variant. Creates or updates Product rows in sync_core.
"""
from __future__ import annotations

import csv
import io


def parse_catalogue_csv(csv_text: str, tenant_id: str = "default") -> dict:
    """
    Parse a CSV string and return structured catalogue data.

    Returns:
        {"products": [...], "errors": [...], "created": N, "updated": N}
    """
    from ..sync_core.models import Product

    reader = csv.DictReader(io.StringIO(csv_text))
    required = {"sku", "style", "color", "size", "mrp_paise"}
    row_num = 0
    products = []
    errors = []
    created = 0
    updated = 0

    for row in reader:
        row_num += 1
        # Validate required fields
        missing = required - set(row.keys())
        if missing:
            errors.append({"row": row_num, "error": f"missing columns: {missing}"})
            continue

        sku = row["sku"].strip()
        if not sku:
            errors.append({"row": row_num, "error": "empty sku"})
            continue

        try:
            mrp = int(row["mrp_paise"])
            if mrp <= 0:
                errors.append({"row": row_num, "error": "mrp must be positive"})
                continue
        except (ValueError, TypeError):
            errors.append({"row": row_num, "error": f"invalid mrp: {row['mrp_paise']}"})
            continue

        product, is_new = Product.objects.update_or_create(
            variant_id=sku,
            defaults={
                "style": row["style"].strip(),
                "color": row["color"].strip(),
                "size": row["size"].strip(),
                "mrp_paise": mrp,
                "season_tag": row.get("season_tag", "").strip(),
            },
        )
        if is_new:
            created += 1
        else:
            updated += 1
        products.append(sku)

    return {
        "products": products,
        "errors": errors,
        "created": created,
        "updated": updated,
        "total_rows": row_num,
    }


def csv_to_scenarios(csv_text: str) -> list:
    """
    Convert CSV rows to tally scenarios (v0.1: one sale voucher per SKU).
    Returns list of dicts suitable for scenario creation.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    scenarios = []
    for row in reader:
        sku = row.get("sku", "").strip()
        if not sku:
            continue
        scenarios.append({
            "sku": sku,
            "description": f"{row.get('style', '')} {row.get('size', '')}",
            "hsn": row.get("hsn_code", "6205"),
            "mrp_paise": int(row.get("mrp_paise", 0)),
        })
    return scenarios
