"""
Retry / DLQ state machine tests.

These drive ``IrpClient`` against a scripted fake target rather than the
probabilistic simulator so every transition is asserted explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from itertools import cycle

import pytest

from irp_client.client import (
    MAX_ATTEMPTS,
    Clock,
    IrpClient,
    StubAuthProvider,
)
from irp_client.generator import TENANTS, build_invoice
from irp_client.models import (
    AttemptOutcome,
    DeadLetter,
    InvoiceSubmission,
    IrpAttempt,
    SubmissionStatus,
)
from irp_client.simulator import IrpResponse, IrpTarget


# ---- fake target driven by a script of responses ----


@dataclass
class ScriptedTarget:
    script: list[IrpResponse]
    calls: list[tuple[str, dict]] = field(default_factory=list)
    _it: "cycle" = None  # noqa: UP037

    def __post_init__(self):
        self._it = iter(self.script)

    def submit(self, tenant_id: str, payload: dict) -> IrpResponse:
        self.calls.append((tenant_id, payload))
        return next(self._it)


# ---- fixtures ----


@pytest.fixture
def tenant():
    return TENANTS[0]


@pytest.fixture
def inv(tenant):
    built = build_invoice(tenant, seq=1)
    return InvoiceSubmission.objects.create(
        tenant_id=tenant.tenant_id,
        invoice_ref=built["invoice_ref"],
        payload=built["payload"],
    )


@pytest.fixture
def fixed_clock():
    t = [datetime(2026, 4, 20, tzinfo=timezone.utc)]
    mono = [1000.0]

    def advance(seconds: float):
        t[0] = t[0] + timedelta(seconds=seconds)
        mono[0] = mono[0] + seconds

    clock = Clock(wall_now=lambda: t[0], mono_now=lambda: mono[0])
    clock.advance = advance  # type: ignore[attr-defined]
    return clock


# ---- happy path ----


@pytest.mark.django_db
def test_clean_submission_registers_on_first_try(inv, fixed_clock):
    target = ScriptedTarget(
        [IrpResponse(200, "", {"Irn": "IRN001", "AckNo": "AN1"})]
    )
    client = IrpClient(target=target, clock=fixed_clock)
    status = client.submit_pending(inv.id)
    assert status == SubmissionStatus.REGISTERED
    inv.refresh_from_db()
    assert inv.irn == "IRN001"
    assert inv.attempts == 1
    assert IrpAttempt.objects.filter(submission=inv).count() == 1


@pytest.mark.django_db
def test_duplicate_is_treated_as_success(inv, fixed_clock):
    target = ScriptedTarget(
        [IrpResponse(200, "2150", {"Irn": "IRNDUP", "AckNo": "ANDUP"})]
    )
    client = IrpClient(target=target, clock=fixed_clock)
    status = client.submit_pending(inv.id)
    assert status == SubmissionStatus.REGISTERED
    inv.refresh_from_db()
    assert inv.irn == "IRNDUP"


# ---- TRANSIENT: retry budget + exhaustion ----


@pytest.mark.django_db
def test_transient_retries_until_success(inv, fixed_clock):
    target = ScriptedTarget(
        [
            IrpResponse(500, "HTTP_500", {}),
            IrpResponse(502, "HTTP_502", {}),
            IrpResponse(200, "", {"Irn": "IRN-OK"}),
        ]
    )
    client = IrpClient(target=target, clock=fixed_clock)

    assert client.submit_pending(inv.id) == SubmissionStatus.PENDING
    inv.refresh_from_db()
    assert inv.next_eligible_at is not None
    fixed_clock.advance(3600)  # fast-forward past any backoff

    assert client.submit_pending(inv.id) == SubmissionStatus.PENDING
    fixed_clock.advance(3600)

    assert client.submit_pending(inv.id) == SubmissionStatus.REGISTERED
    assert IrpAttempt.objects.filter(submission=inv).count() == 3


@pytest.mark.django_db
def test_transient_exhaustion_goes_to_dlq(inv, fixed_clock):
    # MAX_ATTEMPTS worth of TRANSIENT then nothing — state machine must DLQ
    # on the last attempt.
    target = ScriptedTarget(
        [IrpResponse(500, "HTTP_500", {})] * MAX_ATTEMPTS
    )
    client = IrpClient(target=target, clock=fixed_clock)
    for _ in range(MAX_ATTEMPTS):
        status = client.submit_pending(inv.id)
        fixed_clock.advance(3600)
    assert status == SubmissionStatus.DEAD_LETTERED
    dl = DeadLetter.objects.get(submission=inv)
    assert dl.reason == "retry_exhausted"
    assert dl.last_error_class == AttemptOutcome.TRANSIENT


# ---- THROTTLE: no budget consumption ----


@pytest.mark.django_db
def test_throttle_does_not_consume_retry_budget(inv, fixed_clock):
    # 10 throttles (way past MAX_ATTEMPTS) followed by a success must still
    # succeed because throttle doesn't count against the budget.
    n_throttles = MAX_ATTEMPTS + 3
    target = ScriptedTarget(
        [IrpResponse(429, "2244", {}, retry_after_s=5.0)] * n_throttles
        + [IrpResponse(200, "", {"Irn": "IRN-OK"})]
    )
    client = IrpClient(target=target, clock=fixed_clock)
    for _ in range(n_throttles + 1):
        client.submit_pending(inv.id)
        fixed_clock.advance(10)
    inv.refresh_from_db()
    assert inv.status == SubmissionStatus.REGISTERED


# ---- OUTAGE: circuit break ----


@pytest.mark.django_db
def test_outage_opens_circuit_and_recovers(tenant, fixed_clock):
    inv_a = InvoiceSubmission.objects.create(
        tenant_id=tenant.tenant_id,
        invoice_ref="INV-A",
        payload=build_invoice(tenant, seq=10)["payload"],
    )
    inv_b = InvoiceSubmission.objects.create(
        tenant_id=tenant.tenant_id,
        invoice_ref="INV-B",
        payload=build_invoice(tenant, seq=11)["payload"],
    )
    target = ScriptedTarget(
        [
            IrpResponse(503, "HTTP_503", {}),   # opens circuit for tenant
            IrpResponse(200, "", {"Irn": "IRN-B"}),  # post-cooldown call
            IrpResponse(200, "", {"Irn": "IRN-A"}),
        ]
    )
    client = IrpClient(target=target, clock=fixed_clock)

    assert client.submit_pending(inv_a.id) == SubmissionStatus.CIRCUIT_OPEN
    # inv_b must not even attempt during the cooldown — circuit is per-tenant.
    assert client.submit_pending(inv_b.id) == SubmissionStatus.CIRCUIT_OPEN
    assert len(target.calls) == 1

    fixed_clock.advance(120)  # past OUTAGE_COOLDOWN_S
    assert client.submit_pending(inv_b.id) == SubmissionStatus.REGISTERED
    assert client.submit_pending(inv_a.id) == SubmissionStatus.REGISTERED


# ---- SECURITY: refresh + retry once ----


@pytest.mark.django_db
def test_security_refresh_then_retry_success(inv, fixed_clock):
    target = ScriptedTarget(
        [
            IrpResponse(401, "2284", {}),
            IrpResponse(200, "", {"Irn": "IRN-OK"}),
        ]
    )
    auth = StubAuthProvider()
    before = auth.current_token(inv.tenant_id)
    client = IrpClient(target=target, auth=auth, clock=fixed_clock)
    assert client.submit_pending(inv.id) == SubmissionStatus.REGISTERED
    after = auth.current_token(inv.tenant_id)
    assert before != after, "auth provider must have refreshed"


@pytest.mark.django_db
def test_security_two_failures_in_a_row_goes_to_dlq(inv, fixed_clock):
    target = ScriptedTarget(
        [
            IrpResponse(401, "2284", {}),
            IrpResponse(401, "2285", {}),
        ]
    )
    client = IrpClient(target=target, clock=fixed_clock)
    assert client.submit_pending(inv.id) == SubmissionStatus.DEAD_LETTERED
    dl = DeadLetter.objects.get(submission=inv)
    assert dl.reason == "auth_failed"


# ---- BUSINESS / SCHEMA: no retries, straight to DLQ ----


@pytest.mark.parametrize(
    "code,expected_class",
    [
        ("2172", AttemptOutcome.BUSINESS),
        ("2194", AttemptOutcome.BUSINESS),
        ("2211", AttemptOutcome.BUSINESS),
        ("2100", AttemptOutcome.SCHEMA),
        ("2119", AttemptOutcome.SCHEMA),
    ],
)
@pytest.mark.django_db
def test_business_and_schema_errors_dlq_immediately(
    inv, fixed_clock, code, expected_class
):
    target = ScriptedTarget([IrpResponse(400, code, {"ErrorDetails": [{"ErrorCode": code}]})])
    client = IrpClient(target=target, clock=fixed_clock)
    assert client.submit_pending(inv.id) == SubmissionStatus.DEAD_LETTERED
    dl = DeadLetter.objects.get(submission=inv)
    assert dl.last_error_code == code
    assert dl.last_error_class == expected_class
    assert IrpAttempt.objects.filter(submission=inv).count() == 1
