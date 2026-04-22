"""
Data model for the IRP submission pipeline.

Three concerns, three tables:
1. InvoiceSubmission — "we want this invoice registered"
2. IrpAttempt — append-only HTTP attempt records
3. DeadLetter — terminal-state for manual operator resubmit
"""
from __future__ import annotations

from django.db import models


class SubmissionStatus(models.TextChoices):
    PENDING = "pending", "pending"
    IN_FLIGHT = "in_flight", "in_flight"
    REGISTERED = "registered", "registered"
    CIRCUIT_OPEN = "circuit_open", "circuit_open"
    DEAD_LETTERED = "dead_lettered", "dead_lettered"


class AttemptOutcome(models.TextChoices):
    OK = "ok", "ok"
    TRANSIENT = "TRANSIENT", "TRANSIENT"
    THROTTLE = "THROTTLE", "THROTTLE"
    OUTAGE = "OUTAGE", "OUTAGE"
    SECURITY = "SECURITY", "SECURITY"
    BUSINESS = "BUSINESS", "BUSINESS"
    SCHEMA = "SCHEMA", "SCHEMA"
    DUPLICATE = "DUPLICATE", "DUPLICATE"


class InvoiceSubmission(models.Model):
    tenant_id = models.CharField(max_length=64)
    invoice_ref = models.CharField(max_length=64)
    payload = models.JSONField()
    status = models.CharField(
        max_length=20, choices=SubmissionStatus.choices, default=SubmissionStatus.PENDING,
    )
    attempts = models.PositiveIntegerField(default=0)
    next_eligible_at = models.DateTimeField(null=True, blank=True)
    irn = models.CharField(max_length=64, blank=True, default="")
    ack_no = models.CharField(max_length=32, blank=True, default="")
    ack_dt = models.DateTimeField(null=True, blank=True)
    signed_qr = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("tenant_id", "invoice_ref")]
        indexes = [
            models.Index(fields=["status", "next_eligible_at"]),
            models.Index(fields=["tenant_id", "status"]),
        ]


class IrpAttempt(models.Model):
    submission = models.ForeignKey(
        InvoiceSubmission, on_delete=models.CASCADE, related_name="irp_attempts",
    )
    attempt_no = models.PositiveIntegerField()
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField()
    latency_ms = models.PositiveIntegerField()
    http_status = models.IntegerField(null=True, blank=True)
    irp_error_code = models.CharField(max_length=32, blank=True, default="")
    outcome = models.CharField(max_length=12, choices=AttemptOutcome.choices)
    request_id = models.CharField(max_length=64, blank=True, default="")
    response_excerpt = models.TextField(blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["submission", "attempt_no"]),
            models.Index(fields=["outcome", "started_at"]),
        ]


class DeadLetter(models.Model):
    submission = models.OneToOneField(
        InvoiceSubmission, on_delete=models.CASCADE, related_name="dead_letter",
    )
    reason = models.CharField(max_length=64)
    last_error_code = models.CharField(max_length=32, blank=True, default="")
    last_error_class = models.CharField(max_length=12, choices=AttemptOutcome.choices)
    operator_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
