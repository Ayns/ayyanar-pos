"""
Latency + error-class rollups read straight off ``IrpAttempt``.

Kept deliberately small — nothing here that numpy would handle better; we
care about p50/p95/p99 and a per-class histogram. Operators read these to
decide whether SLOs are met.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import AttemptOutcome, IrpAttempt


def _percentile(sorted_values: list[int], pct: float) -> int:
    if not sorted_values:
        return 0
    if pct <= 0:
        return sorted_values[0]
    if pct >= 100:
        return sorted_values[-1]
    # Nearest-rank method; good enough for ops dashboards and simple here.
    k = max(0, min(len(sorted_values) - 1, int(round(pct / 100 * len(sorted_values))) - 1))
    return sorted_values[k]


@dataclass(frozen=True)
class LatencySummary:
    count: int
    p50_ms: int
    p95_ms: int
    p99_ms: int
    max_ms: int


def latency_summary(queryset=None) -> LatencySummary:
    queryset = queryset if queryset is not None else IrpAttempt.objects.all()
    values = sorted(queryset.values_list("latency_ms", flat=True))
    return LatencySummary(
        count=len(values),
        p50_ms=_percentile(values, 50),
        p95_ms=_percentile(values, 95),
        p99_ms=_percentile(values, 99),
        max_ms=values[-1] if values else 0,
    )


def outcome_histogram(queryset=None) -> dict[str, int]:
    from django.db.models import Count

    queryset = queryset if queryset is not None else IrpAttempt.objects.all()
    buckets: dict[str, int] = {o.value: 0 for o in AttemptOutcome}
    rows = (
        queryset.values_list("outcome")
        .annotate(n=Count("id"))
        .values_list("outcome", "n")
    )
    for outcome, count in rows:
        buckets[outcome] = count
    return buckets
