"""
Store-side APIs. Every mutation writes one StockEvent + one SyncOutbox row
in a single transaction. `on_hand` is always a read-time derivation over
StockEvent rows — never stored, never cached on the correctness path.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from django.db import transaction
from django.db.models import Sum

from .models import (
    StockEvent,
    StockEventKind,
    SyncOutbox,
    SyncOutboxStatus,
)


@dataclass
class StoreClock:
    """
    Per-store clock. Wall-clock is observed but not trusted for ordering.
    Lamport is the authoritative per-store monotonic counter used for
    `outbox_id`.

    `wall_offset_seconds` lets the harness inject skew without actually
    moving the OS clock.
    """

    store_id: str
    wall_offset_seconds: float = 0.0
    _lamport: int = 0

    def now(self) -> datetime:
        return datetime.fromtimestamp(
            datetime.now(tz=timezone.utc).timestamp() + self.wall_offset_seconds,
            tz=timezone.utc,
        )

    def tick(self) -> int:
        self._lamport += 1
        return self._lamport


class Till:
    """Single till within a store. Simulates the Electron POS terminal."""

    def __init__(self, store_id: str, clock: Optional[StoreClock] = None):
        self.store_id = store_id
        self.clock = clock or StoreClock(store_id=store_id)
        self._cached_max_outbox: int | None = None

    def _next_outbox_id(self) -> int:
        if self._cached_max_outbox is None:
            last = (
                StockEvent.objects.filter(store_id=self.store_id)
                .order_by("-outbox_id")
                .values_list("outbox_id", flat=True)
                .first()
            )
            self._cached_max_outbox = int(last or 0)
        self._cached_max_outbox += 1
        return self._cached_max_outbox

    @transaction.atomic
    def _append(
        self,
        variant_id: str,
        kind: str,
        delta: int,
        payload: Optional[dict] = None,
    ) -> StockEvent:
        outbox_id = self._next_outbox_id()
        event = StockEvent.objects.create(
            store_id=self.store_id,
            outbox_id=outbox_id,
            variant_id=variant_id,
            kind=kind,
            delta=delta,
            occurred_at_wall=self.clock.now(),
            occurred_at_lamport=self.clock.tick(),
            payload=payload or {},
        )
        SyncOutbox.objects.create(
            store_id=self.store_id,
            outbox_id=outbox_id,
            status=SyncOutboxStatus.PENDING,
        )
        return event

    def record_sale(self, variant_id: str, qty: int, **payload) -> StockEvent:
        if qty <= 0:
            raise ValueError("sale qty must be positive")
        return self._append(variant_id, StockEventKind.SALE, -qty, payload)

    def record_return(self, variant_id: str, qty: int, **payload) -> StockEvent:
        if qty <= 0:
            raise ValueError("return qty must be positive")
        return self._append(variant_id, StockEventKind.RETURN, +qty, payload)

    def record_receive(self, variant_id: str, qty: int, **payload) -> StockEvent:
        if qty <= 0:
            raise ValueError("receive qty must be positive")
        return self._append(variant_id, StockEventKind.RECEIVE, +qty, payload)

    def record_markdown(self, variant_id: str, **payload) -> StockEvent:
        return self._append(variant_id, StockEventKind.MARKDOWN, 0, payload)

    def record_adjustment(
        self, variant_id: str, delta: int, **payload
    ) -> StockEvent:
        return self._append(variant_id, StockEventKind.ADJUSTMENT, delta, payload)


def local_on_hand(store_id: str, variant_id: str) -> int:
    """Store-side derivation. Always queries the full event log."""
    total = (
        StockEvent.objects.filter(store_id=store_id, variant_id=variant_id)
        .aggregate(s=Sum("delta"))
        .get("s")
    )
    return int(total or 0)
