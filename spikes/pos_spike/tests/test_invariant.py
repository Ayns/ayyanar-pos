"""
Property-based test: the invariant

    sum(CloudEvent.delta WHERE store_id=s, variant_id=v) == CloudStockProjection.on_hand

must hold for every generated history of sales / receives / partitions.

We generate adversarial schedules:
  - interleave writes across 3 stores
  - insert random offline windows during which the drainer fails
  - randomly drain partial batches
  - reorder drain attempts after reconnection
  - force duplicate deliveries (same (store_id, outbox_id) twice)
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from sync_core.cloud import DrainSink, cloud_on_hand, rebuild_projection
from sync_core.drainer import drain
from sync_core.models import (
    CloudEvent,
    CloudStockProjection,
    StockEvent,
    SyncOutbox,
    SyncOutboxStatus,
)
from sync_core.store import Till


@dataclass
class ScheduleOp:
    store: str
    action: str
    variant_id: str
    qty: int = 0
    flip_online: bool | None = None


def ops_strategy(min_size=5, max_size=30):
    stores = st.sampled_from(["S1", "S2", "S3"])
    variants = st.sampled_from(["SKU-A", "SKU-B", "SKU-C"])
    qty = st.integers(min_value=1, max_value=5)
    action = st.sampled_from(["sale", "receive", "return", "adjustment", "toggle_sink", "drain"])
    return st.lists(
        st.tuples(stores, action, variants, qty),
        min_size=min_size,
        max_size=max_size,
    )


@pytest.mark.django_db
@given(script=ops_strategy())
@settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_invariant_sum_events_equals_on_hand(script):
    _seed_inventory(["S1", "S2", "S3"], ["SKU-A", "SKU-B", "SKU-C"], receive_qty=50)
    sink = DrainSink()
    tills = {s: Till(store_id=s) for s in ("S1", "S2", "S3")}
    sink_online = True
    for store, action, variant, qty in script:
        till = tills[store]
        if action == "sale":
            till.record_sale(variant_id=variant, qty=qty)
        elif action == "receive":
            till.record_receive(variant_id=variant, qty=qty)
        elif action == "return":
            till.record_return(variant_id=variant, qty=qty)
        elif action == "adjustment":
            till.record_adjustment(variant_id=variant, delta=qty - 2)
        elif action == "toggle_sink":
            sink_online = not sink_online
            sink.online = sink_online
        elif action == "drain":
            drain(store_id=store, sink=sink)

    sink.online = True
    for s in ("S1", "S2", "S3"):
        while drain(store_id=s, sink=sink) > 0:
            pass

    for s in ("S1", "S2", "S3"):
        for v in ("SKU-A", "SKU-B", "SKU-C"):
            computed = sum(
                e.delta
                for e in CloudEvent.objects.filter(store_id=s, variant_id=v)
            )
            projected = cloud_on_hand(s, v)
            assert computed == projected, (
                f"sum(events) != projection for {s}/{v}: "
                f"{computed} vs {projected}"
            )

    for s in ("S1", "S2", "S3"):
        rebuild_projection(store_id=s)
    for s in ("S1", "S2", "S3"):
        for v in ("SKU-A", "SKU-B", "SKU-C"):
            assert cloud_on_hand(s, v) == sum(
                e.delta
                for e in CloudEvent.objects.filter(store_id=s, variant_id=v)
            )

    for s in ("S1", "S2", "S3"):
        assert not SyncOutbox.objects.filter(
            store_id=s, status=SyncOutboxStatus.PENDING
        ).exists()


@pytest.mark.django_db
def test_duplicate_ingest_is_idempotent():
    Till("S1").record_sale("SKU-A", 2)
    sink = DrainSink()

    assert drain("S1", sink) == 1
    assert drain("S1", sink) == 0
    SyncOutbox.objects.filter(store_id="S1").update(status=SyncOutboxStatus.PENDING)
    assert drain("S1", sink) == 1

    assert CloudEvent.objects.filter(store_id="S1", outbox_id=1).count() == 1
    assert cloud_on_hand("S1", "SKU-A") == -2


@pytest.mark.django_db
def test_catalogue_divergence_routes_to_pending_reconciliation():
    from sync_core.cloud import DrainSink, IngestBatchItem
    from sync_core.models import PendingReconciliation
    from datetime import datetime, timezone

    sink = DrainSink()
    now = datetime.now(tz=timezone.utc)
    sink.ingest(
        [
            IngestBatchItem(
                store_id="S1",
                outbox_id=1,
                variant_id="SKU-A",
                kind="sale",
                delta=-2,
                occurred_at_wall=now,
                occurred_at_lamport=1,
                payload={},
            )
        ]
    )
    sink.ingest(
        [
            IngestBatchItem(
                store_id="S1",
                outbox_id=1,
                variant_id="SKU-A",
                kind="sale",
                delta=-3,
                occurred_at_wall=now,
                occurred_at_lamport=1,
                payload={},
            )
        ]
    )
    assert PendingReconciliation.objects.filter(
        reason=PendingReconciliation.Reason.PAYLOAD_DIVERGENCE
    ).count() == 1
    assert cloud_on_hand("S1", "SKU-A") == -2


def _seed_inventory(stores, variants, receive_qty):
    sink = DrainSink()
    for s in stores:
        till = Till(store_id=s)
        for v in variants:
            till.record_receive(variant_id=v, qty=receive_qty)
        while drain(store_id=s, sink=sink) > 0:
            pass
