"""
Cloud-side ingest + projection.

Ingest is idempotent on `(store_id, outbox_id)`. If the same key arrives
twice, the second call is a no-op unless payload/delta differ — in which
case we raise a PAYLOAD_DIVERGENCE anomaly (spike surfaces, does not
silently overwrite).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.db import transaction
from django.db.models import Sum

from .models import (
    CatalogUpdate,
    CloudEvent,
    CloudStockProjection,
    PendingReconciliation,
)


@dataclass
class IngestBatchItem:
    store_id: str
    outbox_id: int
    variant_id: str
    kind: str
    delta: int
    occurred_at_wall: object
    occurred_at_lamport: int
    payload: dict


class DrainSink:
    """
    In-process cloud sink. Toggle `online=False` to simulate a cable-pull.
    """

    def __init__(self) -> None:
        self.online = True

    @transaction.atomic
    def ingest(self, batch: Iterable[IngestBatchItem]) -> list[tuple[str, int]]:
        if not self.online:
            raise ConnectionError("cloud sink offline (pull-the-cable drill)")
        items = list(batch)
        if not items:
            return []
        acks: list[tuple[str, int]] = []
        keys = [(i.store_id, i.outbox_id) for i in items]
        existing_map = {
            (e.store_id, e.outbox_id): e
            for e in CloudEvent.objects.filter(
                store_id__in={s for s, _ in keys},
                outbox_id__in={o for _, o in keys},
            ).only("store_id", "outbox_id", "variant_id", "kind", "delta", "payload")
        }
        to_create: list[CloudEvent] = []
        divergences: list[PendingReconciliation] = []
        projection_delta: dict[tuple[str, str], list[int]] = {}
        for item in items:
            acks.append((item.store_id, item.outbox_id))
            existing = existing_map.get((item.store_id, item.outbox_id))
            if existing is not None:
                if (
                    existing.delta != item.delta
                    or existing.kind != item.kind
                    or existing.variant_id != item.variant_id
                    or existing.payload != item.payload
                ):
                    divergences.append(
                        PendingReconciliation(
                            store_id=item.store_id,
                            outbox_id=item.outbox_id,
                            variant_id=item.variant_id,
                            reason=PendingReconciliation.Reason.PAYLOAD_DIVERGENCE,
                            detail={
                                "existing": {
                                    "kind": existing.kind,
                                    "delta": existing.delta,
                                    "variant_id": existing.variant_id,
                                    "payload": existing.payload,
                                },
                                "incoming": {
                                    "kind": item.kind,
                                    "delta": item.delta,
                                    "variant_id": item.variant_id,
                                    "payload": item.payload,
                                },
                            },
                        )
                    )
                continue
            to_create.append(
                CloudEvent(
                    store_id=item.store_id,
                    outbox_id=item.outbox_id,
                    variant_id=item.variant_id,
                    kind=item.kind,
                    delta=item.delta,
                    occurred_at_wall=item.occurred_at_wall,
                    occurred_at_lamport=item.occurred_at_lamport,
                    payload=item.payload,
                )
            )
            bucket = projection_delta.setdefault(
                (item.store_id, item.variant_id), [0, 0]
            )
            bucket[0] += int(item.delta)
            if item.outbox_id > bucket[1]:
                bucket[1] = item.outbox_id
        if to_create:
            CloudEvent.objects.bulk_create(to_create, batch_size=500)
        if divergences:
            PendingReconciliation.objects.bulk_create(divergences, batch_size=500)
        for (store_id, variant_id), (delta, max_outbox) in projection_delta.items():
            _apply_projection_bulk(
                store_id=store_id,
                variant_id=variant_id,
                delta=delta,
                outbox_id=max_outbox,
            )
        return acks


def _apply_projection_bulk(
    *, store_id: str, variant_id: str, delta: int, outbox_id: int
) -> None:
    proj, _ = CloudStockProjection.objects.get_or_create(
        store_id=store_id, variant_id=variant_id
    )
    proj.on_hand = (proj.on_hand or 0) + int(delta)
    if outbox_id > (proj.last_outbox_id or 0):
        proj.last_outbox_id = outbox_id
    proj.save()
    if proj.on_hand < 0:
        PendingReconciliation.objects.create(
            store_id=store_id,
            outbox_id=outbox_id,
            variant_id=variant_id,
            reason=PendingReconciliation.Reason.NEGATIVE_STOCK,
            detail={"on_hand": proj.on_hand},
        )


def rebuild_projection(store_id: str, variant_id: str | None = None) -> None:
    """
    Disaster-recovery path: drop and recompute CloudStockProjection from
    CloudEvent. Also exercised by the property test to prove the
    projection is consistent with the event log.
    """
    events = CloudEvent.objects.filter(store_id=store_id)
    if variant_id is not None:
        events = events.filter(variant_id=variant_id)
        CloudStockProjection.objects.filter(
            store_id=store_id, variant_id=variant_id
        ).delete()
    else:
        CloudStockProjection.objects.filter(store_id=store_id).delete()
    totals = (
        events.values("variant_id")
        .annotate(on_hand=Sum("delta"))
        .values_list("variant_id", "on_hand")
    )
    last_outbox = {
        row["variant_id"]: row["mx"]
        for row in events.values("variant_id").annotate(mx=Sum("outbox_id"))
    }
    for vid, on_hand in totals:
        max_outbox = (
            events.filter(variant_id=vid).order_by("-outbox_id").values_list("outbox_id", flat=True).first()
            or 0
        )
        CloudStockProjection.objects.create(
            store_id=store_id,
            variant_id=vid,
            on_hand=int(on_hand or 0),
            last_outbox_id=int(max_outbox),
        )


def cloud_on_hand(store_id: str, variant_id: str) -> int:
    proj = CloudStockProjection.objects.filter(
        store_id=store_id, variant_id=variant_id
    ).first()
    return int(proj.on_hand) if proj else 0


def emit_catalog_update(variant_id: str, field: str, new_value) -> CatalogUpdate:
    return CatalogUpdate.objects.create(
        variant_id=variant_id, field=field, new_value=new_value
    )
