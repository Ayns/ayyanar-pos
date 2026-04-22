"""
Event-sourced outbox schema for the AYY-13 R1 spike.

`on_hand` is NEVER stored on the store side; it is derived from sum(delta).
`outbox_id` is a store-local monotonically-increasing sequence.
`(store_id, outbox_id)` is globally unique and is the idempotency key.
"""
from django.db import models


class StockEventKind(models.TextChoices):
    SALE = "sale"
    RECEIVE = "receive"
    MARKDOWN = "markdown"
    ADJUSTMENT = "adjustment"
    RETURN = "return"


class Product(models.Model):
    """Cloud-authoritative catalogue. Local stores pull via change feed."""

    variant_id = models.CharField(max_length=64, primary_key=True)
    style = models.CharField(max_length=64)
    size = models.CharField(max_length=16)
    color = models.CharField(max_length=32)
    mrp_paise = models.BigIntegerField()
    season_tag = models.CharField(max_length=32, blank=True, default="")
    catalogue_version = models.BigIntegerField(default=1)


class StockEvent(models.Model):
    """
    Append-only per-store ledger. `on_hand` is NEVER stored on the store
    side; it is derived from sum(delta) where delta is signed (sales are
    negative, receives positive).

    `outbox_id` is a store-local monotonically-increasing sequence.
    `(store_id, outbox_id)` is globally unique and is the idempotency key
    both store-side and cloud-side.
    """

    store_id = models.CharField(max_length=32)
    outbox_id = models.BigIntegerField()
    variant_id = models.CharField(max_length=64)
    kind = models.CharField(max_length=16, choices=StockEventKind.choices)
    delta = models.IntegerField()
    occurred_at_wall = models.DateTimeField()
    occurred_at_lamport = models.BigIntegerField()
    payload = models.JSONField(default=dict)

    class Meta:
        unique_together = [("store_id", "outbox_id")]
        indexes = [
            models.Index(fields=["store_id", "variant_id"]),
            models.Index(fields=["store_id", "outbox_id"]),
        ]


class SyncOutboxStatus(models.TextChoices):
    PENDING = "pending"
    SENT = "sent"
    ACKED = "acked"


class SyncOutbox(models.Model):
    """
    Shipping queue. One row per StockEvent. Drainer ships PENDING rows to
    cloud and flips to SENT, then to ACKED once cloud confirms ingest.

    Retained after ACKED for pending-reconciliation visibility.
    """

    store_id = models.CharField(max_length=32)
    outbox_id = models.BigIntegerField()
    status = models.CharField(
        max_length=16, choices=SyncOutboxStatus.choices, default=SyncOutboxStatus.PENDING
    )
    attempts = models.IntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")

    class Meta:
        unique_together = [("store_id", "outbox_id")]
        indexes = [models.Index(fields=["store_id", "status"])]


class CloudEvent(models.Model):
    """
    Cloud-side durable copy of a StockEvent. Ingest is idempotent on
    `(store_id, outbox_id)`.
    """

    store_id = models.CharField(max_length=32)
    outbox_id = models.BigIntegerField()
    variant_id = models.CharField(max_length=64)
    kind = models.CharField(max_length=16, choices=StockEventKind.choices)
    delta = models.IntegerField()
    occurred_at_wall = models.DateTimeField()
    occurred_at_lamport = models.BigIntegerField()
    payload = models.JSONField(default=dict)
    ingested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("store_id", "outbox_id")]
        indexes = [
            models.Index(fields=["store_id", "variant_id"]),
            models.Index(fields=["ingested_at"]),
        ]


class CloudStockProjection(models.Model):
    """
    Cloud-side materialized view: `on_hand` per `(store_id, variant_id)`.
    Rebuilt from CloudEvent. NOT the source of truth — CloudEvent is.
    """

    store_id = models.CharField(max_length=32)
    variant_id = models.CharField(max_length=64)
    on_hand = models.BigIntegerField(default=0)
    last_outbox_id = models.BigIntegerField(default=0)

    class Meta:
        unique_together = [("store_id", "variant_id")]


class CatalogUpdate(models.Model):
    """
    Cloud-authoritative catalogue change. Stores pull these via change feed
    ordered by `feed_cursor` and apply to their local Product rows.
    """

    feed_cursor = models.BigAutoField(primary_key=True)
    variant_id = models.CharField(max_length=64)
    field = models.CharField(max_length=32)
    new_value = models.JSONField()
    emitted_at = models.DateTimeField(auto_now_add=True)


class ChangeFeedCursor(models.Model):
    """Each store's position in the cloud catalogue change feed."""

    store_id = models.CharField(max_length=32, primary_key=True)
    cursor = models.BigIntegerField(default=0)


class PendingReconciliation(models.Model):
    """
    Surface for anomalies that the automated flow cannot resolve: negative
    stock after replay, idempotency collisions with divergent payloads,
    large clock skews, etc.
    """

    class Reason(models.TextChoices):
        NEGATIVE_STOCK = "negative_stock"
        PAYLOAD_DIVERGENCE = "payload_divergence"
        LARGE_CLOCK_SKEW = "large_clock_skew"
        UNKNOWN_VARIANT = "unknown_variant"

    store_id = models.CharField(max_length=32)
    outbox_id = models.BigIntegerField(null=True, blank=True)
    variant_id = models.CharField(max_length=64, blank=True, default="")
    reason = models.CharField(max_length=32, choices=Reason.choices)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
