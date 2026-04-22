"""
AYY-34 — E-Invoice (IRP) models.

Implements Section 7.2 of the SRS: IRN generation, QR code, grace period, cancellation.
"""

import uuid
from django.db import models
from django.conf import settings


class InvoiceSubmission(models.Model):
    """Tracks each e-invoice submission to the IRP."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bill = models.ForeignKey("billing.Bill", on_delete=models.PROTECT, related_name="irp_submissions")
    gstrn = models.CharField(max_length=15)  # Seller GSTIN
    invoice_number = models.CharField(max_length=30)  # Bill number

    # IRP response
    irn = models.CharField(max_length=40, blank=True)  # Invoice Reference Number
    qr_code = models.TextField(blank=True)  # Base64 QR code
    ack_number = models.CharField(max_length=30, blank=True)
    ack_date = models.DateTimeField(null=True, blank=True)
    cancel_allowed = models.BooleanField(default=True)  # Within 24h?

    # Status
    STATUS_PENDING = "pending"
    STATUS_IN_FLIGHT = "in_flight"
    STATUS_REGISTERED = "registered"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    status = models.CharField(max_length=20, default=STATUS_PENDING)
    error_code = models.CharField(max_length=20, blank=True)  # IRP error code (2150, 2172, etc.)
    error_message = models.TextField(blank=True)

    # Retry tracking
    retry_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=6)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    circuit_breaker_open = models.BooleanField(default=False)

    # DLQ
    in_dlq = models.BooleanField(default=False)
    dlq_reason = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ayy_irp_submission"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "bill_id"]),
            models.Index(fields=["circuit_breaker_open"]),
        ]

    def __str__(self):
        return f"IRP #{self.invoice_number}: {self.status}"


class IrpAttempt(models.Model):
    """Individual API call attempt to IRP."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(InvoiceSubmission, on_delete=models.CASCADE, related_name="attempts")
    attempt_number = models.PositiveIntegerField()
    request_payload = models.JSONField()
    response_status = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ayy_irp_attempt"
        ordering = ["attempt_number"]


class DeadLetter(models.Model):
    """DLQ for IRP submissions that failed all retries."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.OneToOneField(InvoiceSubmission, on_delete=models.PROTECT)
    final_error_code = models.CharField(max_length=20)
    final_error_message = models.TextField()
    last_attempt_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ayy_irp_dead_letter"


class IRPError(models.Model):
    """Error taxonomy for IRP codes (Section 7.2 + error classification)."""

    code = models.CharField(max_length=20, primary_key=True)
    category = models.CharField(max_length=30)  # DUPLICATE, BUSINESS, SCHEMA, SECURITY, THROTTLE, TRANSIENT, OUTAGE
    description = models.CharField(max_length=200)
    requires_action = models.BooleanField(default=True)
    action_description = models.TextField(blank=True)
    retryable = models.BooleanField(default=False)

    class Meta:
        db_table = "ayy_irp_error_taxonomy"
