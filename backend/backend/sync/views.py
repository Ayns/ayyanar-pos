"""
AYY-34 — Sync views.

Outbox drainer, change-feed replayer, reconciliation console.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import SyncOutbox, CloudEvent, SyncSession, PendingReconciliation


class SyncOutboxViewSet(viewsets.ReadOnlyModelViewSet):
    """View pending and sent outbox items."""

    queryset = SyncOutbox.objects.all()

    def list(self, request):
        store_id = request.query_params.get("store_id", "")
        status_filter = request.query_params.get("status", "pending")

        qs = SyncOutbox.objects.all()
        if store_id:
            qs = qs.filter(store_id=store_id)
        if status_filter:
            qs = qs.filter(status=status_filter)

        qs = qs.order_by("outbox_id")[:100]

        return Response({
            "items": [{
                "id": str(o.id),
                "outbox_id": o.outbox_id,
                "entity_type": o.entity_type,
                "entity_id": str(o.entity_id),
                "payload": o.payload,
                "status": o.status,
                "retries": o.retries,
                "created_at": o.created_at.isoformat(),
            } for o in qs],
            "count": qs.count(),
        })


class SyncDrainView(viewsets.ViewSet):
    """Drain outbox items to cloud (called by Celery task)."""

    @action(detail=False, methods=["post"])
    def drain(self, request):
        """Push pending outbox items to cloud and update status."""
        store_id = request.data.get("store_id", "")
        batch_size = int(request.data.get("batch_size", 50))

        pending = SyncOutbox.objects.filter(
            store_id=store_id, status=SyncOutbox.PENDING
        ).order_by("outbox_id")[:batch_size]

        pushed = 0
        for item in pending:
            # In production, this sends to cloud via HTTPS
            # For prototype, just mark as sent
            item.status = SyncOutbox.SENT
            item.sent_at = None  # auto-set
            item.save()
            pushed += 1

        return Response({"pushed": pushed, "remaining": SyncOutbox.objects.filter(store_id=store_id, status=SyncOutbox.PENDING).count()})


class ReconciliationViewSet(viewsets.ModelViewSet):
    """FR: Review and resolve sync anomalies."""

    queryset = PendingReconciliation.objects.all()
    filter_backends = []

    def list(self, request):
        anomalies = PendingReconciliation.objects.filter(status="open").order_by("-created_at")[:50]
        return Response({
            "anomalies": [{
                "id": str(a.id),
                "anomaly_type": a.anomaly_type,
                "store_id": a.store_id,
                "outbox_id": a.outbox_id,
                "entity_type": a.entity_type,
                "details": a.details,
                "created_at": a.created_at.isoformat(),
            } for a in anomalies],
            "total_open": PendingReconciliation.objects.filter(status="open").count(),
        })

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        anomaly = self.get_object()
        anomaly.status = "resolved"
        anomaly.resolved_at = None  # auto-set
        anomaly.save()
        return Response({"status": "resolved"})


class ChangeFeedCursorViewSet(viewsets.ModelViewSet):
    """Per-store pull position for cloud change-feed."""

    queryset = SyncSession.objects.all()

    def list(self, request):
        store_id = request.query_params.get("store_id", "")
        sessions = SyncSession.objects.filter(store_id=store_id).order_by("-started_at")[:10]
        return Response({
            "sessions": [{
                "id": str(s.id),
                "client_highwater": s.client_lamport_highwater,
                "server_highwater": s.server_lamport_highwater,
                "items_pushed": s.items_pushed,
                "items_pull": s.items_pull,
                "started_at": s.started_at.isoformat(),
                "status": s.status,
            } for s in sessions],
        })
