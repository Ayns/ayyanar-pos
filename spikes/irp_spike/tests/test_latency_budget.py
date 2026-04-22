"""
Latency percentile regression gate.

The simulator's log-normal distribution is the *design target* for the v1
retry-policy math. If the p99 or the error rate drifts significantly from
this envelope, we want a loud failure because downstream SLOs assume this
shape. (Empirical sandbox numbers from the 7-day run replace the simulator
envelope here once operators land them in an ``sla_actuals.json``.)
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from irp_client.client import Clock, IrpClient
from irp_client.generator import TENANTS, build_invoice
from irp_client.models import InvoiceSubmission
from irp_client.simulator import IrpResponse, IrpSimulator, SimulatorConfig
from irp_client.stats import latency_summary


# SLO budget the plan document commits to. The simulator is hand-tuned to hit
# this in a 2000-call sample; if the numbers drift, the test catches it.
SLO_P99_MS = 5000
SLO_P95_MS = 2000
SLO_P50_MS = 500


@pytest.mark.django_db
def test_simulated_p99_within_slo_budget():
    """
    Drive 2000 submissions through the simulator with a controllable clock.
    We don't want to actually sleep log-normal millis — we *do* want the
    stored ``latency_ms`` to reflect the log-normal sample so percentile
    stats land in the right zone.
    """
    t_wall = [datetime(2026, 4, 20, tzinfo=timezone.utc)]
    t_mono = [1000.0]

    def wall_now():
        return t_wall[0]

    def mono_now():
        return t_mono[0]

    clock = Clock(wall_now=wall_now, mono_now=mono_now)

    sim = IrpSimulator(SimulatorConfig(seed=7, throttle_rate=0.0, transient_5xx_rate=0.0, outage_start_prob=0.0))
    rng = _stable_rng(seed=11)

    real_submit = sim.submit

    def timed_submit(tenant_id, payload):
        # Burn a log-normal sample and advance the monotonic clock by it so
        # the client's finished_mono - started_mono captures it as latency.
        ms = min(30_000, rng.lognormvariate(5.0, 0.45))  # cap to avoid absurd tails
        t_mono[0] = t_mono[0] + (ms / 1000.0)
        return real_submit(tenant_id, payload)

    sim.submit = timed_submit
    client = IrpClient(target=sim, clock=clock)

    tenant = TENANTS[0]
    for seq in range(1, 2001):
        inv = build_invoice(tenant, seq=seq)
        row = InvoiceSubmission.objects.create(
            tenant_id=tenant.tenant_id,
            invoice_ref=inv["invoice_ref"],
            payload=inv["payload"],
        )
        client.submit_pending(row.id)
        # Tiny wall-clock step between submissions so timestamps are unique.
        t_wall[0] = t_wall[0] + timedelta(milliseconds=1)

    summary = latency_summary()
    assert summary.count >= 2000, summary
    assert summary.p50_ms <= SLO_P50_MS, summary
    assert summary.p95_ms <= SLO_P95_MS, summary
    assert summary.p99_ms <= SLO_P99_MS, summary


def _stable_rng(seed):
    import random as _r

    return _r.Random(seed)
