"""
Store → cloud drainer. Celery's job in production.

Batch size and backoff are intentionally not tuned. Correctness first.
"""
from __future__ import annotations

from datetime import datetime, timezone

from django.db import transaction
from django.db.models import F

from .cloud import DrainSink, IngestBatchItem
from .models import StockEvent, SyncOutbox, SyncOutboxStatus


def _attempts_plus_one():
    return F("attempts") + 1


def drain(store_id: str, sink: DrainSink, batch_size: int = 200) -> int:
    """
    Ship PENDING outbox rows for the given store. Return the count
    actually acknowledged by cloud. Called repeatedly until it returns 0.
    """
    pending = list(
        SyncOutbox.objects.filter(
            store_id=store_id, status=SyncOutboxStatus.PENDING
        ).order_by("outbox_id")[:batch_size]
    )
    if not pending:
        return 0
    event_rows = {
        (e.store_id, e.outbox_id): e
        for e in StockEvent.objects.filter(
            store_id=store_id,
            outbox_id__in=[p.outbox_id for p in pending],
        )
    }
    batch = [
        IngestBatchItem(
            store_id=p.store_id,
            outbox_id=p.outbox_id,
            variant_id=event_rows[(p.store_id, p.outbox_id)].variant_id,
            kind=event_rows[(p.store_id, p.outbox_id)].kind,
            delta=event_rows[(p.store_id, p.outbox_id)].delta,
            occurred_at_wall=event_rows[(p.store_id, p.outbox_id)].occurred_at_wall,
            occurred_at_lamport=event_rows[(p.store_id, p.outbox_id)].occurred_at_lamport,
            payload=event_rows[(p.store_id, p.outbox_id)].payload,
        )
        for p in pending
    ]
    now = datetime.now(tz=timezone.utc)
    outbox_ids = [p.outbox_id for p in pending]
    try:
        acks = sink.ingest(batch)
    except ConnectionError:
        SyncOutbox.objects.filter(
            store_id=store_id, outbox_id__in=outbox_ids
        ).update(
            attempts=_attempts_plus_one(),
            last_attempt_at=now,
            last_error="offline",
        )
        return 0
    acked_outbox_ids = [oid for (_, oid) in acks]
    with transaction.atomic():
        SyncOutbox.objects.filter(
            store_id=store_id, outbox_id__in=acked_outbox_ids
        ).update(
            status=SyncOutboxStatus.ACKED,
            attempts=_attempts_plus_one(),
            last_attempt_at=now,
            last_error="",
        )
        not_acked = [oid for oid in outbox_ids if oid not in set(acked_outbox_ids)]
        if not_acked:
            SyncOutbox.objects.filter(
                store_id=store_id, outbox_id__in=not_acked
            ).update(
                attempts=_attempts_plus_one(),
                last_attempt_at=now,
                last_error="partial",
            )
    return len(acked_outbox_ids)
