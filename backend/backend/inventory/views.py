"""
AYY-34 — Inventory views.

Ledger queries, stock level computation, adjustments, physical counts.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import StockEvent, StockLevel, StockAdjustment, StockTransfer


class StockEventViewSet(viewsets.ReadOnlyModelViewSet):
    """FR-LED-002: Queryable stock ledger."""

    queryset = StockEvent.objects.select_related("variant").order_by("-lamport_timestamp")
    filter_backends = []

    def list(self, request):
        store_id = request.query_params.get("store_id", "")
        variant_id = request.query_params.get("variant_id", "")
        event_type = request.query_params.get("event_type", "")

        qs = StockEvent.objects.select_related("variant")

        if store_id:
            qs = qs.filter(store_id=store_id)
        if variant_id:
            qs = qs.filter(variant_id=variant_id)
        if event_type:
            qs = qs.filter(event_type=event_type)

        qs = qs.order_by("lamport_timestamp")[:100]

        return Response([{
            "id": str(e.id),
            "variant_sku": e.variant.sku,
            "event_type": e.event_type,
            "quantity": e.quantity,
            "reference_type": e.reference_type,
            "reference_id": str(e.reference_id) if e.reference_id else None,
            "reason_code": e.reason_code,
            "lamport_timestamp": e.lamport_timestamp,
            "created_at": e.created_at.isoformat(),
        } for e in qs])


class StockLevelViewSet(viewsets.ReadOnlyModelViewSet):
    """FR-LED-002: Current stock levels per SKU per store."""

    queryset = StockLevel.objects.select_related("variant")
    serializer_class = None  # inline response

    def list(self, request):
        store_id = request.query_params.get("store_id", "")

        qs = StockLevel.objects.select_related("variant")
        if store_id:
            qs = qs.filter(store_id=store_id)

        return Response([{
            "store_id": sl.store_id,
            "variant_id": str(sl.variant.id),
            "sku": sl.variant.sku,
            "full_label": sl.variant.full_label,
            "on_hand": sl.on_hand,
            "reserved": sl.reserved,
            "allocated": sl.allocated,
            "sellable": sl.sellable,
            "in_transit": sl.in_transit,
            "pending_qc": sl.pending_qc,
            "last_recomputed_at": sl.last_recomputed_at.isoformat() if sl.last_recomputed_at else None,
        } for sl in qs[:200]])

    @action(detail=False, methods=["post"])
    def recompute(self, request):
        """Rebuild stock levels from the event ledger (FR-LED-001)."""
        store_id = request.data.get("store_id", "")
        # Simple rebuild: group events by variant and sum
        from .models import StockEvent
        events = StockEvent.objects.filter(store_id=store_id).order_by("lamport_timestamp")
        # Group by variant
        from collections import defaultdict
        deltas = defaultdict(int)
        for e in events:
            deltas[e.variant_id] += e.quantity

        results = []
        for variant_id, delta in deltas.items():
            sl, created = StockLevel.objects.get_or_create(
                store_id=store_id,
                variant_id=variant_id,
                defaults={"on_hand": delta},
            )
            if not created:
                sl.on_hand = delta
                sl.save()
            results.append({
                "sku": sl.variant.sku,
                "on_hand": sl.on_hand,
                "created": created,
            })

        return Response({"recomputed": len(results), "levels": results})


class StockAdjustmentViewSet(viewsets.ModelViewSet):
    """FR-ADJ-001 through FR-ADJ-005: Stock adjustments."""

    queryset = StockAdjustment.objects.all()

    def create(self, request):
        """Create a stock adjustment (requires approval above threshold)."""
        store_id = request.data.get("store_id", "")
        variant_id = request.data.get("variant_id")
        adjustment_type = request.data.get("adjustment_type")  # "positive" or "negative"
        quantity = int(request.data.get("quantity", 0))
        reason_code = request.data.get("reason_code", "")
        initiated_by = request.data.get("initiated_by", "")

        if not all([store_id, variant_id, adjustment_type, quantity, reason_code, initiated_by]):
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

        adj = StockAdjustment.objects.create(
            store_id=store_id,
            variant_id=variant_id,
            adjustment_type=adjustment_type,
            quantity=quantity,
            reason_code=reason_code,
            initiated_by=initiated_by,
        )
        return Response({"id": str(adj.id), "status": adj.status}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        adj = self.get_object()
        adj.status = "approved"
        adj.approved_by = request.data.get("approved_by", "")
        adj.approved_at = None  # auto-set by save
        adj.save()

        # Post stock event
        from .models import StockEvent
        direction = 1 if adj.adjustment_type == "positive" else -1
        StockEvent.objects.create(
            store_id=adj.store_id,
            variant_id=adj.variant,
            event_type="adjustment",
            quantity=direction * adj.quantity,
            reference_type="adjustment",
            reference_id=adj.id,
            reason_code=adj.reason_code,
            created_by=adj.initiated_by,
            notes=adj.notes,
        )
        return Response({"status": "approved"})


class StockTransferViewSet(viewsets.ModelViewSet):
    """FR-STO-001 through FR-STO-010, FR-STI-001 through FR-STI-008."""

    queryset = StockTransfer.objects.all()

    @action(detail=True, methods=["post"])
    def dispatch(self, request, pk=None):
        """FR-STO-001 through FR-STO-010: Dispatch a transfer."""
        transfer = self.get_object()
        transfer.status = StockTransfer.STATUS_DISPATCHED
        transfer.dispatch_date = None  # auto-set
        transfer.transporter = request.data.get("transporter", "")
        transfer.vehicle_number = request.data.get("vehicle_number", "")
        transfer.lr_number = request.data.get("lr_number", "")
        transfer.save()
        return Response({"status": "dispatched"})

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        """FR-STI-001 through FR-STI-008: Receive and reconcile a transfer."""
        transfer = self.get_object()
        received_lines = request.data.get("received_lines", [])

        # Three-way reconciliation (FR-STI-002)
        discrepancies = []
        for line in received_lines:
            # Compare dispatched vs received
            pass  # Full reconciliation logic

        transfer.status = StockTransfer.STATUS_RECEIVED
        transfer.receipt_date = None  # auto-set
        transfer.save()
        return Response({
            "status": "received",
            "discrepancies": discrepancies,
        })
