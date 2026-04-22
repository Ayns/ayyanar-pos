"""AYY-27 — Views for sync_core (stock, outbox, catalogue)."""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Sum

from .models import (
    Product,
    StockEvent,
    SyncOutbox,
    PendingReconciliation,
)


def catalogue_list(request):
    """List all catalogue variants."""
    products = Product.objects.all().values(
        "variant_id", "style", "size", "color", "mrp_paise",
        "season_tag", "catalogue_version",
    )
    return JsonResponse(list(products), safe=False)


def catalogue_detail(request, variant_id):
    """Get a single catalogue variant."""
    try:
        p = Product.objects.get(variant_id=variant_id)
    except Product.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)
    return JsonResponse({
        "variant_id": p.variant_id,
        "style": p.style,
        "size": p.size,
        "color": p.color,
        "mrp_paise": p.mrp_paise,
        "season_tag": p.season_tag,
        "catalogue_version": p.catalogue_version,
    })


def stock_on_hand(request, variant_id):
    """Derived stock count for a variant (sum of deltas)."""
    total = StockEvent.objects.filter(
        variant_id=variant_id
    ).aggregate(total=Sum("delta"))["total"] or 0
    return JsonResponse({"variant_id": variant_id, "on_hand": total})


def stock_events_list(request):
    """List stock events (paginated)."""
    page = int(request.GET.get("page", 1))
    per_page = int(request.GET.get("per_page", 50))
    start = (page - 1) * per_page
    events = StockEvent.objects.all().order_by("-outbox_id")[start:start + per_page]
    total = StockEvent.objects.count()
    return JsonResponse({
        "results": list(events.values()),
        "total": total,
        "page": page,
        "per_page": per_page,
    })


@require_http_methods(["POST"])
def drain_outbox(request):
    """Trigger an outbox drain cycle. Celery runs this in production."""
    from .drainer import drain
    from .cloud import DrainSink

    store_id = request.POST.get("store_id", "local")
    sink = DrainSink()
    acked = drain(store_id, sink)
    return JsonResponse({"store_id": store_id, "acked": acked})


# Celery task wrapper for the drainer
def celery_drain(store_id: str, batch_size: int = 200) -> int:
    """Celery task entry point for the outbox drainer."""
    from .drainer import drain
    from .cloud import DrainSink
    return drain(store_id, DrainSink(), batch_size)


def outbox_status(request):
    """Current outbox status counts."""
    pending = SyncOutbox.objects.filter(status="pending").count()
    sent = SyncOutbox.objects.filter(status="sent").count()
    acked = SyncOutbox.objects.filter(status="acked").count()
    return JsonResponse({"pending": pending, "sent": sent, "acked": acked})


def pending_reconciliation_list(request):
    """Surface unresolved reconciliation anomalies."""
    unresolved = PendingReconciliation.objects.filter(resolved_at__isnull=True)
    return JsonResponse(
        list(unresolved.values("id", "store_id", "variant_id", "reason", "detail", "created_at")),
        safe=False,
    )
