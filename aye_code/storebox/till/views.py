"""AYY-27 — Till POS views (v0.1).

Uses the Till class from the local sync_core module. The Till.record_sale()
takes (variant_id, qty) and emits a single SALE event per call.
The checkout view aggregates cart lines into individual events.
"""
import json
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.http import JsonResponse
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from sync_core.store import Till as StoreTill
from sync_core.models import Product, StockEvent, StockEventKind, SyncOutbox

_PAISSA = Decimal("0.01")


def _get_till():
    """Get a Till instance for the current store."""
    store_id = getattr(settings, "STORE_ID", "store-0001")
    return StoreTill(store_id)


def till_home(request):
    """Till main screen — shows catalogue for selection."""
    products = Product.objects.all().values(
        "variant_id", "style", "color", "size", "mrp_paise",
    )
    return JsonResponse(list(products), safe=False)


@csrf_exempt
@require_http_methods(["POST"])
def cart_add(request):
    """Add item to cart. Body: variant_id, qty."""
    data = json.loads(request.body)
    variant_id = data["variant_id"]
    qty = int(data.get("qty", 1))

    try:
        product = Product.objects.get(variant_id=variant_id)
    except Product.DoesNotExist:
        return JsonResponse({"error": "variant not found"}, status=404)

    cart = request.session.get("cart", [])
    found = False
    for line in cart:
        if line["variant_id"] == variant_id:
            line["qty"] += qty
            found = True
            break
    if not found:
        cart.append({
            "variant_id": variant_id,
            "qty": qty,
            "unit_price_paise": product.mrp_paise,
        })
    request.session["cart"] = cart
    return JsonResponse({"cart": cart})


@csrf_exempt
@require_http_methods(["POST"])
def cart_remove(request):
    """Remove item from cart. Body: variant_id."""
    data = json.loads(request.body)
    variant_id = data["variant_id"]
    cart = request.session.get("cart", [])
    cart = [c for c in cart if c["variant_id"] != variant_id]
    request.session["cart"] = cart
    return JsonResponse({"cart": cart})


def _compute_gst(unit_price_paise, qty, hsn_code, customer_gstin, state_of_supply="Karnataka"):
    """Compute CGST/SGST (intra-state) or IGST (inter-state) for a line item.

    v0.1: auto-detect intra vs inter state from customer GSTIN state code.
    Returns dict with base_paise, cgst_paise, sgst_paise, igst_paise, gst_total_paise.
    """
    gross_paise = Decimal(unit_price_paise) * qty
    # v0.1: default to 12% GST rate (covers most apparel)
    gst_rate = Decimal("0.12")

    if customer_gstin and len(customer_gstin) >= 2:
        customer_state_code = int(customer_gstin[:2])
        # Default store state is Karnataka (29); if customer differs, it's inter-state
        store_state = getattr(settings, "STORE_GSTIN_STATE", "29")
        if customer_state_code != int(store_state):
            state_of_supply = "interstate"

    base_paise = gross_paise / (Decimal(1) + gst_rate)
    base_paise = base_paise.quantize(_PAISSA, rounding=ROUND_HALF_UP)
    gst_total_paise = (gross_paise - base_paise).quantize(_PAISSA, rounding=ROUND_HALF_UP)

    if state_of_supply == "interstate":
        return {
            "base_paise": int(base_paise),
            "igst_paise": int(gst_total_paise),
            "cgst_paise": 0,
            "sgst_paise": 0,
            "gst_total_paise": int(gst_total_paise),
            "hsn_code": hsn_code,
        }
    else:
        half = gst_total_paise / 2
        sgst = gst_total_paise - half
        return {
            "base_paise": int(base_paise),
            "igst_paise": 0,
            "cgst_paise": int(half),
            "sgst_paise": int(sgst),
            "gst_total_paise": int(gst_total_paise),
            "hsn_code": hsn_code,
        }


@csrf_exempt
@require_http_methods(["POST"])
def checkout_view(request):
    """
    Complete a sale: deduct stock, emit StockEvent per line, generate receipt.
    Body: {
        "payments": [{"method": "CASH", "amount_paise": 5000}, ...],
        "discount_paise": 0,
        "customer_name": "Walk-in",
        "customer_gstin": "",
        "lines": [{"variant_id": "...", "qty": 1, "hsn_code": "6109"}],
    }
    """
    data = json.loads(request.body)
    cart = request.session.get("cart", [])
    if not cart:
        return JsonResponse({"error": "empty cart"}, status=400)

    payments = data.get("payments", [{"method": "CASH", "amount_paise": 999999}])
    discount_paise = int(data.get("discount_paise", 0))
    customer_name = data.get("customer_name", "Walk-in")
    customer_gstin = data.get("customer_gstin", "")
    lines_input = data.get("lines", cart)
    total_paid = sum(p["amount_paise"] for p in payments)

    till = _get_till()

    with transaction.atomic():
        invoice_no = None
        gst_lines = []
        for line in cart:
            variant_id = line["variant_id"]
            qty = line["qty"]
            hsn_code = line.get("hsn_code", "")

            # Record sale (emits StockEvent + SyncOutbox)
            till.record_sale(variant_id, qty, payment=payments)

            # Compute GST for this line
            gst = _compute_gst(line["unit_price_paise"], qty, hsn_code, customer_gstin)
            gst_lines.append(gst)

            # Track the first outbox_id as this invoice's number
            if invoice_no is None:
                last = StockEvent.objects.filter(
                    store_id=till.store_id,
                ).order_by("-outbox_id").values_list("outbox_id", flat=True).first()
                invoice_no = int(last or 0)

        # Clear cart
        request.session["cart"] = []

    return JsonResponse({
        "status": "ok",
        "invoice_no": invoice_no,
        "total_paid_paise": total_paid,
        "discount_paise": discount_paise,
        "customer_name": customer_name,
        "gst_lines": gst_lines,
        "cart": [],
    })


def receipt_view(request, invoice_id):
    """Return a receipt JSON for a given invoice ID."""
    events = StockEvent.objects.filter(
        outbox_id=invoice_id,
    )
    if not events.exists():
        return JsonResponse({"error": "invoice not found"}, status=404)

    return JsonResponse({
        "invoice_id": invoice_id,
        "events": list(events.values()),
    })
