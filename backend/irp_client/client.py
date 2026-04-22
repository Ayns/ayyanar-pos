"""
The IRP client state machine — production version of the AYY-14 R2 spike.

State transitions:
    pending       -> in_flight -> registered  (terminal)
    in_flight     -> pending      (TRANSIENT, backoff)
    in_flight     -> dead_lettered (retry exhausted)
    in_flight     -> pending      (THROTTLE, Retry-After)
    in_flight     -> circuit_open (OUTAGE)
    circuit_open  -> pending      (cooldown elapsed)
    in_flight     -> re-auth, retry once; else dead_lettered (SECURITY)
    in_flight     -> dead_lettered  (BUSINESS/SCHEMA, terminal)
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from django.db import transaction
from django.utils import timezone as djtz

from .error_taxonomy import ErrorClass, classify
from .models import (
    AttemptOutcome,
    DeadLetter,
    InvoiceSubmission,
    IrpAttempt,
    SubmissionStatus,
)
from .simulator import IrpResponse, IrpTarget


MAX_ATTEMPTS = 6
BASE_BACKOFF_S = 2.0
MAX_BACKOFF_S = 300.0
OUTAGE_COOLDOWN_S = 60.0


class AuthProvider(Protocol):
    def current_token(self, tenant_id: str) -> str: ...
    def refresh(self, tenant_id: str) -> None: ...


class StubAuthProvider:
    """Spike stand-in. Production swaps in the real GSTN auth flow."""

    def __init__(self) -> None:
        self._tokens: dict[str, str] = {}

    def current_token(self, tenant_id: str) -> str:
        return self._tokens.setdefault(tenant_id, f"stub-token-{tenant_id}")

    def refresh(self, tenant_id: str) -> None:
        self._tokens[tenant_id] = f"stub-token-{tenant_id}-{random.randint(1, 10**9)}"


@dataclass
class Clock:
    """Tests want deterministic time."""
    wall_now: "callable[[], datetime]" = lambda: djtz.now()
    mono_now: "callable[[], float]" = time.monotonic


@dataclass
class TenantCircuit:
    """Per-tenant cooldown. Populated when OUTAGE class fires."""
    open_until: datetime | None = None

    def is_open(self, wall_now: datetime) -> bool:
        return self.open_until is not None and wall_now < self.open_until

    def open(self, wall_now: datetime, cooldown_s: float) -> None:
        self.open_until = wall_now + timedelta(seconds=cooldown_s)

    def close(self) -> None:
        self.open_until = None


class IrpClient:
    """
    Owns one (target, auth provider) pair. All mutation is DB-level
    (Django's DB layer is the actual synchronisation point).
    """

    def __init__(
        self,
        target: IrpTarget,
        auth: AuthProvider | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.target = target
        self.auth = auth or StubAuthProvider()
        self.clock = clock or Clock()
        self._circuits: dict[str, TenantCircuit] = {}

    def submit_pending(self, submission_id: int) -> str:
        """Drive a single submission one step. Safe to call on any status."""
        sub = InvoiceSubmission.objects.get(pk=submission_id)
        if sub.status in (
            SubmissionStatus.REGISTERED,
            SubmissionStatus.DEAD_LETTERED,
        ):
            return sub.status

        circuit = self._circuit(sub.tenant_id)
        wall_now = self.clock.wall_now()
        if circuit.is_open(wall_now):
            sub.status = SubmissionStatus.CIRCUIT_OPEN
            sub.next_eligible_at = circuit.open_until
            sub.save(update_fields=["status", "next_eligible_at", "updated_at"])
            return sub.status
        if sub.status == SubmissionStatus.CIRCUIT_OPEN and not circuit.is_open(wall_now):
            sub.status = SubmissionStatus.PENDING
            sub.save(update_fields=["status", "updated_at"])

        return self._attempt(sub, auth_retries=1)

    def _attempt(self, sub: InvoiceSubmission, auth_retries: int) -> str:
        sub.status = SubmissionStatus.IN_FLIGHT
        sub.save(update_fields=["status", "updated_at"])

        started_wall = self.clock.wall_now()
        started_mono = self.clock.mono_now()
        try:
            resp = self.target.submit(sub.tenant_id, sub.payload)
        except Exception as exc:
            resp = IrpResponse(
                http_status=0,
                error_code="NET_TIMEOUT" if "timeout" in str(exc).lower() else "NET_CONN_RESET",
                body={"error": str(exc)[:200]},
            )
        finished_wall = self.clock.wall_now()
        finished_mono = self.clock.mono_now()
        latency_ms = max(0, int((finished_mono - started_mono) * 1000))

        outcome = self._outcome_for(resp)
        IrpAttempt.objects.create(
            submission=sub,
            attempt_no=sub.attempts + 1,
            started_at=started_wall,
            finished_at=finished_wall,
            latency_ms=latency_ms,
            http_status=resp.http_status,
            irp_error_code=resp.error_code,
            outcome=outcome,
            request_id=resp.request_id,
            response_excerpt=str(resp.body)[:400],
        )
        sub.attempts += 1

        if outcome == AttemptOutcome.OK:
            return self._finish_ok(sub, resp)
        if outcome == AttemptOutcome.DUPLICATE:
            return self._finish_ok(sub, resp, duplicate=True)
        if outcome == AttemptOutcome.TRANSIENT:
            return self._schedule_retry(sub, resp, finished_wall)
        if outcome == AttemptOutcome.THROTTLE:
            return self._schedule_throttle(sub, resp, finished_wall)
        if outcome == AttemptOutcome.OUTAGE:
            return self._open_circuit(sub, finished_wall)
        if outcome == AttemptOutcome.SECURITY:
            return self._handle_security(sub, auth_retries)
        return self._dead_letter(sub, resp, outcome)

    def _outcome_for(self, resp: IrpResponse) -> str:
        if resp.error_code == "":
            return AttemptOutcome.OK
        cls = classify(resp.error_code)
        return {
            ErrorClass.TRANSIENT: AttemptOutcome.TRANSIENT,
            ErrorClass.THROTTLE: AttemptOutcome.THROTTLE,
            ErrorClass.OUTAGE: AttemptOutcome.OUTAGE,
            ErrorClass.SECURITY: AttemptOutcome.SECURITY,
            ErrorClass.BUSINESS: AttemptOutcome.BUSINESS,
            ErrorClass.SCHEMA: AttemptOutcome.SCHEMA,
            ErrorClass.DUPLICATE: AttemptOutcome.DUPLICATE,
        }[cls]

    def _finish_ok(
        self, sub: InvoiceSubmission, resp: IrpResponse, duplicate: bool = False
    ) -> str:
        body = resp.body or {}
        sub.status = SubmissionStatus.REGISTERED
        sub.irn = body.get("Irn", "") or sub.irn
        sub.ack_no = body.get("AckNo", "") or sub.ack_no
        ack_dt = body.get("AckDt")
        if ack_dt and not sub.ack_dt:
            try:
                sub.ack_dt = datetime.strptime(ack_dt, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                pass
        sub.signed_qr = body.get("SignedQRCode", "") or sub.signed_qr
        sub.next_eligible_at = None
        sub.save()
        return sub.status

    def _schedule_retry(
        self, sub: InvoiceSubmission, resp: IrpResponse, now_wall: datetime
    ) -> str:
        if sub.attempts >= MAX_ATTEMPTS:
            return self._dead_letter(sub, resp, AttemptOutcome.TRANSIENT, reason="retry_exhausted")
        backoff = _compute_backoff(sub.attempts)
        sub.status = SubmissionStatus.PENDING
        sub.next_eligible_at = now_wall + timedelta(seconds=backoff)
        sub.save(update_fields=["status", "attempts", "next_eligible_at", "updated_at"])
        return sub.status

    def _schedule_throttle(
        self, sub: InvoiceSubmission, resp: IrpResponse, now_wall: datetime
    ) -> str:
        wait = resp.retry_after_s if resp.retry_after_s is not None else 30.0
        sub.attempts = max(0, sub.attempts - 1)
        sub.status = SubmissionStatus.PENDING
        sub.next_eligible_at = now_wall + timedelta(seconds=wait)
        sub.save(update_fields=["status", "attempts", "next_eligible_at", "updated_at"])
        return sub.status

    def _open_circuit(self, sub: InvoiceSubmission, now_wall: datetime) -> str:
        circuit = self._circuit(sub.tenant_id)
        circuit.open(now_wall, OUTAGE_COOLDOWN_S)
        sub.attempts = max(0, sub.attempts - 1)
        sub.status = SubmissionStatus.CIRCUIT_OPEN
        sub.next_eligible_at = circuit.open_until
        sub.save(update_fields=["status", "attempts", "next_eligible_at", "updated_at"])
        return sub.status

    def _handle_security(self, sub: InvoiceSubmission, auth_retries: int) -> str:
        if auth_retries <= 0:
            return self._dead_letter(
                sub,
                IrpResponse(401, "2285", {"error": "auth_failed"}),
                AttemptOutcome.SECURITY,
                reason="auth_failed",
            )
        self.auth.refresh(sub.tenant_id)
        return self._attempt(sub, auth_retries=auth_retries - 1)

    def _dead_letter(
        self,
        sub: InvoiceSubmission,
        resp: IrpResponse,
        last_class: str,
        reason: str | None = None,
    ) -> str:
        with transaction.atomic():
            sub.status = SubmissionStatus.DEAD_LETTERED
            sub.next_eligible_at = None
            sub.save()
            DeadLetter.objects.update_or_create(
                submission=sub,
                defaults={
                    "reason": reason or _default_reason(last_class),
                    "last_error_code": resp.error_code,
                    "last_error_class": last_class,
                },
            )
        return sub.status

    def _circuit(self, tenant_id: str) -> TenantCircuit:
        return self._circuits.setdefault(tenant_id, TenantCircuit())


def _compute_backoff(attempts: int) -> float:
    """Exponential backoff with full jitter, capped at MAX_BACKOFF_S."""
    cap = min(MAX_BACKOFF_S, BASE_BACKOFF_S * (2 ** max(0, attempts - 1)))
    return random.uniform(0, cap)


def _default_reason(last_class: str) -> str:
    return {
        AttemptOutcome.BUSINESS: "business_error",
        AttemptOutcome.SCHEMA: "schema_error",
        AttemptOutcome.SECURITY: "auth_failed",
        AttemptOutcome.TRANSIENT: "retry_exhausted",
    }.get(last_class, "unknown")
