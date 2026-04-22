"""
AYY-34 — Tally models.

Tracks daily voucher exports for Tally integration.
"""

import uuid
from django.db import models
from django.conf import settings


class DailyVoucherLog(models.Model):
    """Log of daily Tally XML exports."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store_id = models.CharField(max_length=20, default=settings.STORE_ID)
    date = models.DateField()
    xml_content = models.TextField()  # Tally-compatible XML
    tally_version = models.CharField(max_length=20, default="erp_9")  # erp_9, prime, prime_server
    total_bills = models.PositiveIntegerField(default=0)
    total_sales_paise = models.PositiveIntegerField(default=0)
    total_tax_paise = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, default="pending")  # pending, generated, sent, failed
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ayy_tally_voucher_log"
        unique_together = [("store_id", "date")]
        ordering = ["-date"]

    def __str__(self):
        return f"Tally {self.store_id} {self.date}: {self.status}"
