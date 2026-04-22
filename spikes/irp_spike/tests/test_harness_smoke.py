"""
End-to-end smoke: enqueue a single simulated day for 5 tenants, pump the
submit loop to quiescence, and sanity-check the resulting state.

This is the fast-check version of the 7-day sandbox run the operator runs
out-of-band. Numbers here are small (1 day instead of 7, defect rate bumped
so DLQ exercises have material to chew on) but every piece of pipeline fires.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from irp_client.client import Clock, IrpClient
from irp_client.harness import HarnessConfig, SubmissionHarness
from irp_client.models import InvoiceSubmission, SubmissionStatus
from irp_client.simulator import IrpSimulator, SimulatorConfig
from irp_client.stats import latency_summary, outcome_histogram


@pytest.mark.django_db
def test_one_day_five_tenants_runs_cleanly(settings):
    # Fast, deterministic-ish clock for the pump.
    t_wall = [datetime(2026, 4, 20, tzinfo=timezone.utc)]

    def wall_now():
        return t_wall[0]

    clock = Clock(wall_now=wall_now)
    sim = IrpSimulator(
        SimulatorConfig(
            seed=99,
            throttle_rate=0.0,
            transient_5xx_rate=0.0,
            outage_start_prob=0.0,
        )
    )
    client = IrpClient(target=sim, clock=clock)
    harness = SubmissionHarness(
        client=client,
        config=HarnessConfig(
            tenants_count=5,
            invoices_per_tenant_per_day=40,
            days=1,
            defect_rate=0.10,
            seed=99,
        ),
    )

    enqueued = harness.enqueue_day(0)
    assert enqueued == 5 * 40

    steps = harness.pump(max_iterations=5000)
    assert steps > 0

    total = InvoiceSubmission.objects.count()
    registered = InvoiceSubmission.objects.filter(
        status=SubmissionStatus.REGISTERED
    ).count()
    dlq = InvoiceSubmission.objects.filter(
        status=SubmissionStatus.DEAD_LETTERED
    ).count()

    # Every row must be terminal (success or DLQ) once the pump quiesces.
    assert registered + dlq == total, (
        f"non-terminal rows left: total={total} ok={registered} dlq={dlq}"
    )
    # With 10% defect rate, DLQ must be non-empty to prove the path fires.
    assert dlq > 0

    summary = latency_summary()
    assert summary.count >= total  # at least 1 attempt per submission

    hist = outcome_histogram()
    # At least one OK and at least one non-OK outcome logged.
    assert hist["ok"] > 0
    non_ok = sum(v for k, v in hist.items() if k != "ok")
    assert non_ok > 0
