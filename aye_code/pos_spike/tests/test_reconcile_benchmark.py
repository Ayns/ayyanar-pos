"""
Reconcile-time benchmark. Success criterion from AYY-13:

    "Reconcile time after a 7-day offline window: <30s for a 5k-line/day
     store profile."

5k lines/day × 7 days = 35 000 events per store. We measure the drainer
wall-clock from cable-reconnect to fully-drained outbox on one store.
"""
from __future__ import annotations

import random
import time

import pytest

from sync_core.cloud import DrainSink, cloud_on_hand
from sync_core.drainer import drain
from sync_core.models import StockEvent, SyncOutbox, SyncOutboxStatus
from sync_core.store import Till


@pytest.mark.django_db(transaction=True)
def test_reconcile_7day_5k_per_day_under_30s():
    sink = DrainSink()
    t = Till("S1")
    rnd = random.Random(42)

    t.record_receive("SKU-A", 100_000)
    while drain("S1", sink) > 0:
        pass

    LINES = 35_000
    sink.online = False
    for _ in range(LINES):
        t.record_sale("SKU-A", rnd.randint(1, 2))

    assert StockEvent.objects.filter(store_id="S1").count() == LINES + 1
    assert (
        SyncOutbox.objects.filter(
            store_id="S1", status=SyncOutboxStatus.PENDING
        ).count()
        == LINES
    )

    sink.online = True
    started = time.monotonic()
    drained_total = 0
    while True:
        n = drain("S1", sink, batch_size=1000)
        drained_total += n
        if n == 0:
            break
    elapsed = time.monotonic() - started
    pending = SyncOutbox.objects.filter(
        store_id="S1", status=SyncOutboxStatus.PENDING
    ).count()
    assert pending == 0
    assert drained_total == LINES
    print(
        f"\n[benchmark] 7-day/5k-line reconcile: {elapsed:.2f}s for {LINES} events"
    )
    assert elapsed < 30.0, f"reconcile too slow: {elapsed:.2f}s > 30s"

    expected = sum(
        e.delta for e in StockEvent.objects.filter(store_id="S1", variant_id="SKU-A")
    )
    assert cloud_on_hand("S1", "SKU-A") == expected
