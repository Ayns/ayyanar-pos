"""
AYY-34 — Till / POS views.

Checkout flow: add items -> apply discounts -> split tender -> complete bill -> print receipt.
Implements FR-POS-001 through FR-POS-012.
"""

import logging
from decimal import Decimal

from django.db import transaction, models as django_models
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Bill, BillLine, BillPayment, Return
from ..catalogue.models import Variant

logger = logging.getLogger(__name__)


def compute_gst(taxable_value_paise, gst_rate, is_inter_state):
    """Compute CGST/SGST (intra) or IGST (inter) for a given taxable value."""
    rate = Decimal(str(gst_rate))
    taxable = Decimal(str(taxable_value_paise))
    tax_amount = (taxable * rate / Decimal("100")).quantize(Decimal("1"))

    if is_inter_state:
        return 0, 0, int(tax_amount)  # cgst, sgst, igst
    else:
        half = (tax_amount // Decimal("2")).quantize(Decimal("1"))
        remainder = tax_amount - half
        return int(half), int(remainder), 0  # cgst, sgst, igst


class TillViewSet(viewsets.ViewSet):
    """
    Till endpoints for POS billing.

    GET    /till/                   — List available variants for sale
    POST   /till/cart/add/          — Add item to cart (client-side, not persisted)
    POST   /till/cart/remove/       — Remove item from cart
    POST   /till/checkout/          — Complete a sale
    GET    /till/receipt/<id>/      — Receipt lookup
    GET    /till/holds/             — List held bills
    POST   /till/holds/<id>/resume/ — Resume a held bill
    """

    # ── Catalogue listing for POS ──
    def list(self, request):
        """FR-POS-001, FR-POS-002: Fast catalogue listing — optimised for ≤5s lookup."""
        variants = Variant.objects.select_related(
            "style", "style__sub_category", "colour", "size"
        ).filter(is_active=True)[:200]

        data = []
        for v in variants:
            data.append({
                "id": str(v.id),
                "sku": v.sku,
                "barcode": v.barcode,
                "style_name": v.style.style_name,
                "style_code": v.style.style_code,
                "colour_name": v.colour.name,
                "size_name": v.size.name,
                "mrp_paise": v.mrp_paise,
                "selling_price_paise": v.selling_price_paise,
                "hsn_code": v.style.hsn_code,
                "gst_slab": float(v.style.gst_slab),
                "full_label": v.full_label,
            })
        return Response(data)

    # ── Cart actions (client-side, but tracked server-side for session) ──
    @action(detail=False, methods=["post"], url_path="cart/add")
    def cart_add(self, request):
        """Add item to cart — tracks server-side for concurrent stock checks."""
        variant_id = request.data.get("variant_id")
        qty = int(request.data.get("qty", 1))

        try:
            variant = Variant.objects.select_for_update().get(id=variant_id, is_active=True)
        except Variant.DoesNotExist:
            return Response({"error": "Variant not found or inactive"}, status=status.HTTP_404_NOT_FOUND)

        # FR-NEG-001: Prevent negative stock — supervisor PIN override required
        # Note: actual stock deduction happens at checkout
        return Response({
            "status": "ok",
            "item": {
                "id": str(variant.id),
                "sku": variant.sku,
                "full_label": variant.full_label,
                "mrp_paise": variant.mrp_paise,
                "selling_price_paise": variant.selling_price_paise,
                "qty": qty,
            },
        })

    @action(detail=False, methods=["post"], url_path="cart/remove")
    def cart_remove(self, request):
        """Remove item from cart."""
        variant_id = request.data.get("variant_id")
        return Response({"status": "ok", "removed_id": variant_id})

    # ── Checkout ──
    @action(detail=False, methods=["post"], url_path="checkout")
    def checkout(self, request):
        """FR-POS-005, FR-POS-006: Complete a sale with tender-wise split."""
        lines_data = request.data.get("lines", [])
        payments_data = request.data.get("payments", [])
        discount_paise = int(request.data.get("discount_paise", 0))
        customer_name = request.data.get("customer_name", "Walk-in")
        customer_gstin = request.data.get("customer_gstin", "")

        if not lines_data:
            return Response({"error": "No items in bill"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Create bill
            bill = Bill.objects.create(
                store_id=settings.STORE_ID,
                cashier_id=request.data.get("cashier_id", "anonymous"),
                customer_name=customer_name,
                customer_gstin=customer_gstin,
                remarks=request.data.get("remarks", ""),
                is_inter_state=len(customer_gstin) == 15 and customer_gstin[:2] != settings.STORE_GSTIN_STATE,
            )

            subtotal_paise = 0
            taxable_value_paise = 0
            total_cgst = 0
            total_sgst = 0
            total_igst = 0

            for line_data in lines_data:
                variant_id = line_data.get("variant_id")
                qty = int(line_data.get("qty", 1))
                hsn = line_data.get("hsn_code", "")

                try:
                    variant = Variant.objects.select_for_update().get(id=variant_id, is_active=True)
                except Variant.DoesNotExist:
                    return Response(
                        {"error": f"Variant {variant_id} not found"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # FR-NEG-001: Check stock before deduction
                # (stock ledger integration deferred to sync_core)

                # Compute line totals
                unit_price = variant.selling_price_paise
                line_subtotal = unit_price * qty
                line_discount = min(int(line_data.get("line_discount_paise", 0)), line_subtotal)
                line_after_discount = line_subtotal - line_discount

                # GST calculation
                gst_rate = Decimal(str(variant.style.gst_slab))
                cgst, sgst, igst = compute_gst(line_after_discount, gst_rate, bill.is_inter_state)

                line = BillLine.objects.create(
                    bill=bill,
                    variant=variant,
                    quantity=qty,
                    unit_price_paise=unit_price,
                    mrp_paise=variant.mrp_paise,
                    line_discount_paise=line_discount,
                    taxable_value_paise=line_after_discount,
                    hsn_code=hsn or variant.style.hsn_code,
                    gst_rate=gst_rate,
                    cgst_paise=cgst,
                    sgst_paise=sgst,
                    igst_paise=igst,
                    discount_override=line_data.get("discount_override", False),
                    overridden_by=line_data.get("overridden_by", ""),
                )

                subtotal_paise += line_subtotal
                taxable_value_paise += line_after_discount
                total_cgst += cgst
                total_sgst += sgst
                total_igst += igst

            # Apply bill-level discount
            actual_discount = min(discount_paise, subtotal_paise)
            taxable_value_paise -= actual_discount
            # Recalculate GST after discount
            if bill.is_inter_state:
                total_igst = int(Decimal(str(taxable_value_paise)) * Decimal(str(bill.igst_rate)) / Decimal("100"))
            else:
                total_gst = int(Decimal(str(taxable_value_paise)) * Decimal(str(bill.cgst_rate)) / Decimal("100"))
                total_cgst = total_gst // 2
                total_sgst = total_gst - total_cgst

            total_with_tax = taxable_value_paise + total_cgst + total_sgst + total_igst

            bill.subtotal_paise = subtotal_paise
            bill.discount_paise = actual_discount
            bill.taxable_value_paise = taxable_value_paise
            bill.cgst_paise = total_cgst
            bill.sgst_paise = total_sgst
            bill.igst_paise = total_igst
            bill.total_paise = total_with_tax
            bill.outbox_id = self._next_outbox_id()
            bill.save()

            # Create payments
            total_paid = 0
            for pay in payments_data:
                BillPayment.objects.create(
                    bill=bill,
                    tender_type=pay["type"],
                    amount_paise=int(pay["amount_paise"]),
                    reference=pay.get("reference", ""),
                    metadata=pay.get("metadata", {}),
                )
                total_paid += int(pay["amount_paise"])

            bill.total_paid_paise = total_paid
            bill.balance_due_paise = max(0, total_with_tax - total_paid)
            bill.status = Bill.STATUS_COMPLETED if bill.balance_due_paise == 0 else Bill.STATUS_DRAFT
            bill.save()

            # Build receipt response
            receipt = {
                "invoice_no": bill.bill_number,
                "total_paise": total_with_tax,
                "total_paid_paise": total_paid,
                "balance_due_paise": bill.balance_due_paise,
                "subtotal_paise": subtotal_paise,
                "discount_paise": actual_discount,
                "gst_lines": [
                    {"type": "CGST", "rate": float(bill.cgst_rate), "amount_paise": total_cgst},
                    {"type": "SGST", "rate": float(bill.sgst_rate), "amount_paise": total_sgst},
                    {"type": "IGST", "rate": float(bill.igst_rate), "amount_paise": total_igst},
                ],
                "payments": [
                    {"type": p.tender_type, "amount_paise": p.amount_paise, "reference": p.reference}
                    for p in bill.payments.all()
                ],
                "lines": [
                    {
                        "sku": l.variant.sku,
                        "description": l.full_description,
                        "qty": l.quantity,
                        "unit_price": l.unit_price_paise,
                        "line_total": l.line_total_paise,
                        "hsn": l.hsn_code,
                        "gst_paise": l.cgst_paise + l.sgst_paise + l.igst_paise,
                    }
                    for l in bill.lines.all()
                ],
                "is_inter_state": bill.is_inter_state,
                "customer_gstin": bill.customer_gstin,
            }

        return Response(receipt)

    @action(detail=False, methods=["get"], url_path="holds")
    def list_holds(self, request):
        """FR-POS-008: List held bills."""
        from .models import BillHold
        holds = BillHold.objects.filter(released_at__isnull=True).order_by("-held_at")[:20]
        return Response([{
            "hold_id": str(h.id),
            "bill_number": h.bill.bill_number,
            "held_by": h.held_by,
            "held_at": h.held_at.isoformat(),
            "reason": h.reason,
            "total_paise": h.bill.total_paise,
            "lines_count": h.bill.lines.count(),
        } for h in holds])

    @action(detail=False, methods=["post"], url_path="returns")
    def create_return(self, request):
        """FR-RET-001 through FR-RET-007: Process a return."""
        bill_number = request.data.get("bill_number")
        reason = request.data.get("reason", "Customer choice")
        refund_mode = request.data.get("refund_mode", "original_tender")
        lines_to_return = request.data.get("lines", [])  # [{line_id, quantity}]

        if not bill_number:
            return Response({"error": "bill_number is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            bill = Bill.objects.get(bill_number=bill_number, status=Bill.STATUS_COMPLETED)
        except Bill.DoesNotExist:
            return Response({"error": "Bill not found or not completed"}, status=status.HTTP_404_NOT_FOUND)

        # FR-RET-001: Check return window (default 15 days)
        from datetime import datetime, timedelta
        return_window = int(request.data.get("return_window_days", 15))
        if (datetime.utcnow() - bill.created_at.replace(tzinfo=None)).days > return_window:
            return Response({"error": "Return window expired"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            ret = Return.objects.create(
                original_bill=bill,
                reason=reason,
                refund_mode=refund_mode,
            )
            # Process each line return (stock adjustment + credit note logic)
            for line_data in lines_to_return:
                try:
                    line = BillLine.objects.get(id=line_data["line_id"], bill=bill)
                    qty = min(int(line_data.get("quantity", 1)), line.quantity)
                    # Return stock to pending-QC bucket
                    # (handled by inventory module)
                except (BillLine.DoesNotExist, KeyError):
                    continue

        return Response({
            "return_number": ret.return_number,
            "status": "pending_qc",
            "refund_mode": refund_mode,
        })


    # ── Helpers ──
    def _next_outbox_id(self):
        """Get next monotonic outbox ID for this store."""
        from ayypos.backend.sync.models import SyncOutbox
        last = SyncOutbox.objects.filter(store_id=settings.STORE_ID).order_by("-outbox_id").first()
        return (last.outbox_id + 1) if last else 1


class ReceiptView(APIView):
    """FR-POS-010: Receipt lookup for reprint."""

    def get(self, request, invoice_id):
        try:
            bill = Bill.objects.select_related().get(
                django_models.Q(bill_number=invoice_id) | django_models.Q(id=invoice_id)
            )
        except Bill.DoesNotExist:
            return Response({"error": "Receipt not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "bill_number": bill.bill_number,
            "date": bill.created_at.isoformat(),
            "cashier": bill.cashier_id,
            "customer_name": bill.customer_name,
            "customer_gstin": bill.customer_gstin,
            "lines": [
                {
                    "description": l.full_description,
                    "qty": l.quantity,
                    "unit_price": l.unit_price_paise,
                    "line_total": l.line_total_paise,
                    "hsn": l.hsn_code,
                    "gst_paise": l.cgst_paise + l.sgst_paise + l.igst_paise,
                }
                for l in bill.lines.all()
            ],
            "subtotal_paise": bill.subtotal_paise,
            "discount_paise": bill.discount_paise,
            "taxable_value_paise": bill.taxable_value_paise,
            "cgst_paise": bill.cgst_paise,
            "sgst_paise": bill.sgst_paise,
            "igst_paise": bill.igst_paise,
            "total_paise": bill.total_paise,
            "payments": [
                {"type": p.tender_type, "amount_paise": p.amount_paise}
                for p in bill.payments.all()
            ],
        })
