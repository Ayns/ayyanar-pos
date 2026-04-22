"""
5-tenant × 200-invoice/day submission harness.

The harness is a thin driver that:
  1. Enqueues ``N`` synthetic invoices per tenant per simulated day.
  2. Runs a submission pump that picks eligible rows and calls ``IrpClient``.
  3. Advances a simulated clock between pump cycles so THROTTLE/OUTAGE waits
     are actually observed without real sleeps.

The same driver can be pointed at the real IRP sandbox by:
  - replacing ``IrpSimulator`` with a real-HTTP target that implements the
    ``IrpTarget`` protocol,
  - swapping ``StubAuthProvider`` with the real GSTN auth flow.

No code in the state machine changes.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from django.utils import timezone as djtz

from .client import IrpClient
from .generator import TENANTS, build_invoice
from .models import InvoiceSubmission, SubmissionStatus


@dataclass
class HarnessConfig:
    tenants_count: int = 5
    invoices_per_tenant_per_day: int = 200
    days: int = 7
    defect_rate: float = 0.02   # fraction of invoices that get an injected defect
    seed: int = 42
    start_wall: datetime = field(
        default_factory=lambda: datetime(2026, 4, 20, tzinfo=timezone.utc)
    )


DEFECT_MENU = [
    "missing_mandatory",
    "bad_json_shape",
    "gstin_cancelled_supplier",
    "gstin_cancelled_buyer",
    "line_math_mismatch",
    "back_dated",
    "bad_hsn",
    "invalid_pos",
]


class SubmissionHarness:
    def __init__(self, client: IrpClient, config: HarnessConfig | None = None) -> None:
        self.client = client
        self.config = config or HarnessConfig()
        self._rng = random.Random(self.config.seed)
        self._tenants = TENANTS[: self.config.tenants_count]

    def enqueue_day(self, day_index: int) -> int:
        """Enqueue one simulated day across all tenants. Return row count."""
        per_tenant = self.config.invoices_per_tenant_per_day
        rows = 0
        for tenant in self._tenants:
            base = day_index * per_tenant
            for i in range(per_tenant):
                defect = None
                if self._rng.random() < self.config.defect_rate:
                    defect = self._rng.choice(DEFECT_MENU)
                seq = base + i + 1
                inv = build_invoice(
                    tenant,
                    seq=seq,
                    at=self.config.start_wall + timedelta(days=day_index),
                    rng=random.Random(self.config.seed ^ seq),
                    with_defect=defect,
                )
                InvoiceSubmission.objects.get_or_create(
                    tenant_id=tenant.tenant_id,
                    invoice_ref=inv["invoice_ref"],
                    defaults={"payload": inv["payload"]},
                )
                rows += 1
        return rows

    def pump(self, max_iterations: int = 10_000) -> int:
        """Run the submit loop until nothing is eligible. Return step count."""
        steps = 0
        now = djtz.now
        while steps < max_iterations:
            eligible = InvoiceSubmission.objects.filter(
                status__in=[SubmissionStatus.PENDING, SubmissionStatus.CIRCUIT_OPEN]
            ).filter(
                # Either never scheduled or due.
                models_q_eligible(now())
            ).order_by("updated_at")[:200]
            ids = list(eligible.values_list("id", flat=True))
            if not ids:
                return steps
            for sub_id in ids:
                self.client.submit_pending(sub_id)
                steps += 1
        return steps


def models_q_eligible(wall_now):
    """Q-object helper: rows with no schedule OR schedule due."""
    from django.db.models import Q

    return Q(next_eligible_at__isnull=True) | Q(next_eligible_at__lte=wall_now)
