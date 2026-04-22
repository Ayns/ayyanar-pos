"""Tally export tracking models for storebox."""
from django.db import models


class DailyVoucherLog(models.Model):
    """Track which days have been exported to Tally XML."""
    store_id = models.CharField(max_length=32)
    date = models.DateField()
    xml_path = models.CharField(max_length=512, blank=True, default="")
    xml_sha256 = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("store_id", "date")]
        ordering = ["-date"]
