"""AYY-30 — HO Console REST API views (multi-tenant prototype)."""
import uuid
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Sum

from .models import (
    Tenant, Store, HocUser, StockTransfer,
    PendingReconciliation, CatalogueUpdate, ChangeFeedCursor,
)


# ── Tenants ──

def tenant_list(request):
    tenants = Tenant.objects.all().values("id", "name", "active", "licence_expiry", "created_at")
    return JsonResponse(list(tenants), safe=False)


@require_http_methods(["POST"])
def tenant_create(request):
    body = _json(request)
    tenant = Tenant.objects.create(name=body["name"])
    return JsonResponse({"id": str(tenant.id), "name": tenant.name, "active": True}, status=201)


def tenant_detail(request, pk):
    try:
        tenant = Tenant.objects.get(pk=pk)
    except Tenant.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)

    if request.method == "DELETE":
        tenant.delete()
        return JsonResponse({"deleted": True})

    return JsonResponse({"id": str(tenant.id), "name": tenant.name, "active": tenant.active})


# ── Stores ──

def store_list(request):
    stores = Store.objects.select_related("tenant").values(
        "id", "name", "tenant__name", "city",
    )
    return JsonResponse(list(stores), safe=False)


@require_http_methods(["POST"])
def store_create(request):
    body = _json(request)
    tenant = Tenant.objects.get(pk=body["tenantId"])
    store = Store.objects.create(
        id=body["name"].lower().replace(" ", "-")[:16] + f"-{Store.objects.count()+1:03d}",
        tenant=tenant,
        name=body["name"],
        city=body.get("city", ""),
    )
    return JsonResponse({"id": store.id, "name": store.name, "tenant": tenant.name}, status=201)


# ── Catalogue ──

def catalogue_list(request):
    variants = []
    for product in __import__("pos_spike.sync_core.models", fromlist=["Product"]).Product.objects.all():
        variants.append({
            "variantId": product.variant_id,
            "style": product.style,
            "color": product.color,
            "size": product.size,
            "mrpPaise": product.mrp_paise,
            "seasonTag": product.season_tag,
            "catalogueVersion": product.catalogue_version,
        })
    return JsonResponse(variants, safe=False)


@require_http_methods(["POST"])
def catalogue_push(request):
    """Push a catalogue change to the feed."""
    body = _json(request)
    tenant_id = body.get("tenantId", Tenant.objects.first().id)
    tenant = Tenant.objects.get(pk=tenant_id)
    update = CatalogueUpdate.objects.create(
        tenant=tenant,
        variant_id=body["variantId"],
        field=body["field"],
        new_value=body["newValue"],
    )
    return JsonResponse({"feedCursor": update.feed_cursor}, status=201)


# ── Users ──

def user_list(request):
    users = HocUser.objects.select_related("tenant").values(
        "id", "email", "name", "role",
        "tenant__name", "assigned_stores", "active",
    )
    return JsonResponse(list(users), safe=False)


@require_http_methods(["POST"])
def user_create(request):
    body = _json(request)
    tenant = Tenant.objects.get(pk=body["tenantId"])
    user = HocUser.objects.create(
        tenant=tenant,
        email=body["email"],
        name=body["name"],
        role=body["role"],
        assigned_stores=body.get("storeIds", []),
    )
    return JsonResponse({"id": str(user.id), "email": user.email, "name": user.name, "role": user.role}, status=201)


@require_http_methods(["PATCH"])
def user_detail(request, pk):
    try:
        user = HocUser.objects.get(pk=pk)
    except HocUser.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)

    body = _json(request)
    if "role" in body:
        user.role = body["role"]
    if "storeIds" in body:
        user.assigned_stores = body["storeIds"]
    if "active" in body:
        user.active = body["active"]
    user.save()
    return JsonResponse({"id": str(user.id), "role": user.role, "active": user.active})


@require_http_methods(["DELETE"])
def user_delete(request, pk):
    try:
        HocUser.objects.get(pk=pk).delete()
        return JsonResponse({"deleted": True})
    except HocUser.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)


# ── Stock Transfers ──

def stock_transfer_list(request):
    transfers = StockTransfer.objects.select_related("tenant", "from_store", "to_store").values(
        "id", "from_store__name", "to_store__name",
        "from_store_id", "to_store_id", "items", "status", "created_at",
    )
    return JsonResponse(list(transfers), safe=False)


@require_http_methods(["POST"])
def stock_transfer_create(request):
    body = _json(request)
    tenant = Tenant.objects.first()  # prototype: first tenant
    from_store = Store.objects.get(id=body["fromStoreId"])
    to_store = Store.objects.get(id=body["toStoreId"])
    transfer = StockTransfer.objects.create(
        tenant=tenant,
        from_store=from_store,
        to_store=to_store,
        items=body["items"],
    )
    return JsonResponse({"id": str(transfer.id), "status": transfer.status}, status=201)


@require_http_methods(["POST"])
def stock_transfer_approve(request, pk):
    t = StockTransfer.objects.get(pk=pk)
    t.status = StockTransfer.Status.APPROVED
    t.save()
    return JsonResponse({"id": str(t.id), "status": t.status})


@require_http_methods(["POST"])
def stock_transfer_reject(request, pk):
    t = StockTransfer.objects.get(pk=pk)
    t.status = StockTransfer.Status.REJECTED
    t.save()
    return JsonResponse({"id": str(t.id), "status": t.status})


# ── Reconciliation ──

def reconciliation_list(request):
    items = PendingReconciliation.objects.select_related("tenant", "store").values(
        "id", "store__name", "store_id", "variant_id", "reason", "detail",
        "resolved_at", "created_at",
    )
    return JsonResponse(list(items), safe=False)


@require_http_methods(["POST"])
def reconciliation_approve(request, pk):
    item = PendingReconciliation.objects.get(pk=pk)
    item.resolved_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    item.save()
    return JsonResponse({"id": str(item.id), "resolvedAt": str(item.resolved_at)})


@require_http_methods(["POST"])
def reconciliation_dispute(request, pk):
    item = PendingReconciliation.objects.get(pk=pk)
    item.reason = f"{item.reason} (disputed)"
    item.save()
    return JsonResponse({"id": str(item.id), "reason": item.reason})


# ── Daily Sales ──

def daily_sales(request):
    date = request.GET.get("date", __import__("datetime").date.today().isoformat())
    # Aggregate from sync_core StockEvents
    StockEvent = __import__("pos_spike.sync_core.models", fromlist=["StockEvent"]).StockEvent
    events = StockEvent.objects.filter(occurred_at_wall__date=date)

    from django.db.models import Count
    by_store = events.values("store_id").annotate(
        total=Sum("delta"),
        count=Count("id"),
    )

    return JsonResponse({
        "date": date,
        "stores": [
            {"storeId": e["store_id"], "totalSales": e["total"] or 0, "transactionCount": e["count"]}
            for e in by_store
        ],
    })


# ── Change Feed ──

def change_feed_cursors(request):
    cursors = ChangeFeedCursor.objects.select_related("store").values(
        "store_id", "cursor", "last_sync",
    )
    return JsonResponse(list(cursors), safe=False)


# ── Helpers ──

def _json(request):
    import json
    return json.loads(request.body)
