"""
AYY-34 — Sync models.

Outbox-driven store-to-cloud sync with idempotent ingest.
Implements the offline-sync protocol from Section 11.3 of the SRS.
"""

import uuid
from django.db import models
from django.conf import settings


class SyncOutbox(models.Model):
    """Store-side outbox — writes are buffered here before shipping to cloud."""

    PENDING = "pending"
    SENT = "sent"
    ACKED = "acked"

    STATUS_CHOICES = [(PENDING, "Pending"), (SENT, "Sent"), (ACKED, "Acked")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store_id = models.CharField(max_length=20, default=settings.STORE_ID)
    entity_type = models.CharField(max_length=50)  # "bill", "return", "adjustment", etc.
    entity_id = models.UUIDField()
    payload = models.JSONField()
    outbox_id = models.PositiveBigIntegerField(default=0)  # Lamport counter
    status = models.CharField(max_length=20, default=PENDING, choices=STATUS_CHOICES)
    error_message = models.TextField(blank=True)
    retries = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    acked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ayy_sync_outbox"
        ordering = ["outbox_id"]
        unique_together = [("store_id", "outbox_id")]
        indexes = [
            models.Index(fields=["store_id", "status", "outbox_id"]),
            models.Index(fields=["entity_type", "entity_id"]),
        ]

    def __str__(self):
        return f"#{self.outbox_id} {self.entity_type} ({self.status})"


class CloudEvent(models.Model):
    """Cloud-side idempotent ingest record."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cloud_event_id = models.UUIDField(unique=True)
    entity_type = models.CharField(max_length=50)
    entity_id = models.UUIDField()
    payload = models.JSONField()
    source_store_id = models.CharField(max_length=20)
    ingested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ayy_sync_cloud_event"
        unique_together = [("cloud_event_id", "entity_type")]


class SyncSession(models.Model):
    """Tracks sync sessions for monitoring."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store_id = models.CharField(max_length=20, default=settings.STORE_ID)
    client_lamport_highwater = models.PositiveBigIntegerField(default=0)
    server_lamport_highwater = models.PositiveBigIntegerField(default=0)
    items_pushed = models.PositiveIntegerField(default=0)
    items_pull = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default="running")

    class Meta:
        db_table = "ayy_sync_session"
        ordering = ["-started_at"]


class PendingReconciliation(models.Model):
    """
    Anomaly surface for sync conflicts.

    PAYLOAD_DIVERGENCE: same outbox_id, different payload
    NEGATIVE_STOCK: stock dropped below zero
    ORPHAN_EVENT: cloud event with no source store record
    DUPLICATE_ACK: server ACKed the same outbox_id twice
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store_id = models.CharField(max_length=20, default=settings.STORE_ID)
    anomaly_type = models.CharField(max_length=50)
    outbox_id = models.PositiveBigIntegerField(null=True, blank=True)
    entity_type = models.CharField(max_length=50, blank=True)
    entity_id = models.UUIDField(null=True, blank=True)
    details = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default="open")  # open, resolved, dismissed
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ayy_sync_reconciliation"
        ordering = ["-created_at"]
