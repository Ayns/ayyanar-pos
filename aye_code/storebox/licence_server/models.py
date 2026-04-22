"""
Licence server prototype — AYY-25.

Each store box needs a valid licence to operate. The licence is a time-bound
JWT signed by the HO cloud. The store validates the JWT locally; if expired
or invalid, the till goes read-only.
"""
from __future__ import annotations

from django.db import models


class StoreLicence(models.Model):
    """
    Licence issued to a store box. Contains:
    - store_id (which store this is for)
    - plan (starter | growth)
    - expires_at (when the licence expires)
    - features (JSON set of enabled feature flags)
    - signature (JWT signature, verified on store box)
    """
    store_id = models.CharField(max_length=64, unique=True)
    plan = models.CharField(max_length=32, default="starter")
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    features = models.JSONField(default=dict)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "expires_at"]),
            models.Index(fields=["revoked_at"]),
        ]

    def is_active(self) -> bool:
        if self.revoked_at:
            return False
        from django.utils import timezone
        return timezone.now() < self.expires_at
