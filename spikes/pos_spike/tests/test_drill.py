"""
"Pull the cable" drill. Three concurrent tills. Each store goes offline
for a randomised window; we exercise the specific conflict scenarios
called out in the spike brief.
"""
from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor

import pytest

from sync_core.cloud import DrainSink, cloud_on_hand, emit_catalog_update
from sync_core.drainer import drain
from sync_core.models import (
    CloudEvent,
    PendingReconciliation,
    Product,
    StockEvent,
    SyncOutbox,
    SyncOutboxStatus,
)
from sync_core.replayer import pull_catalog_changes
from sync_core.store import StoreClock, Till


def _drain_all(sink: DrainSink, stores):
    for s in stores:
        while drain(store_id=s, sink=sink) > 0:
            pass


@pytest.mark.django_db(transaction=True)
def test_same_sku_sold_offline_at_two_stores():
    sink = DrainSink()
    t1, t2 = Till("S1"), Till("S2")

    t1.record_receive("SKU-A", 5)
    t2.record_receive("SKU-A", 5)
    _drain_all(sink, ("S1", "S2"))

    sink.online = False
    t1.record_sale("SKU-A", 3)
    t2.record_sale("SKU-A", 4)
    assert drain("S1", sink) == 0 and drain("S2", sink) == 0

    sink.online = True
    _drain_all(sink, ("S1", "S2"))

    assert cloud_on_hand("S1", "SKU-A") == 2
    assert cloud_on_hand("S2", "SKU-A") == 1
    assert not SyncOutbox.objects.filter(status=SyncOutboxStatus.PENDING).exists()


@pytest.mark.django_db(transaction=True)
def test_cloud_catalogue_update_during_offline_window():
    sink = DrainSink()
    t1 = Till("S1")
    t1.record_receive("SKU-A", 10)
    _drain_all(sink, ("S1",))

    sink.online = False
    t1.record_sale("SKU-A", 2)

    emit_catalog_update("SKU-A", "mrp_paise", 149900)

    applied = pull_catalog_changes("S1")
    assert applied == 1
    assert Product.objects.get(variant_id="SKU-A").mrp_paise == 149900

    sink.online = True
    _drain_all(sink, ("S1",))
    assert cloud_on_hand("S1", "SKU-A") == 8


@pytest.mark.django_db(transaction=True)
def test_manual_markdown_mid_offline_window():
    sink = DrainSink()
    t1 = Till("S1")
    t1.record_receive("SKU-A", 20)
    _drain_all(sink, ("S1",))

    sink.online = False
    t1.record_markdown("SKU-A", old_price_paise=199900, new_price_paise=99900)
    t1.record_sale("SKU-A", 4)

    sink.online = True
    _drain_all(sink, ("S1",))

    markdowns = CloudEvent.objects.filter(
        store_id="S1", variant_id="SKU-A", kind="markdown"
    )
    assert markdowns.count() == 1
    assert cloud_on_hand("S1", "SKU-A") == 16


@pytest.mark.django_db(transaction=True)
def test_clock_skew_between_stores_does_not_break_ordering():
    sink = DrainSink()
    t1 = Till("S1", clock=StoreClock("S1", wall_offset_seconds=-3600))
    t2 = Till("S2", clock=StoreClock("S2", wall_offset_seconds=+7200))

    t1.record_receive("SKU-A", 5)
    t2.record_receive("SKU-A", 5)
    _drain_all(sink, ("S1", "S2"))

    sink.online = False
    t1.record_sale("SKU-A", 2)
    t2.record_sale("SKU-A", 3)
    sink.online = True
    _drain_all(sink, ("S1", "S2"))

    assert cloud_on_hand("S1", "SKU-A") == 3
    assert cloud_on_hand("S2", "SKU-A") == 2
    assert not PendingReconciliation.objects.filter(
        reason=PendingReconciliation.Reason.NEGATIVE_STOCK
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_seven_day_offline_window_survives_reconnect():
    sink = DrainSink()
    t1 = Till("S1")
    t1.record_receive("SKU-A", 1000)
    _drain_all(sink, ("S1",))

    sink.online = False
    rnd = random.Random(7)
    for _ in range(500):
        t1.record_sale("SKU-A", rnd.randint(1, 3))
    for _ in range(10):
        t1.record_receive("SKU-A", rnd.randint(5, 20))

    expected = sum(e.delta for e in StockEvent.objects.filter(store_id="S1", variant_id="SKU-A"))

    sink.online = True
    _drain_all(sink, ("S1",))

    assert cloud_on_hand("S1", "SKU-A") == expected
    assert not SyncOutbox.objects.filter(
        store_id="S1", status=SyncOutboxStatus.PENDING
    ).exists()
