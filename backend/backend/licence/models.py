"""
AYY-34 — Licence management.

JWT-like HMAC-SHA256 signed licence tokens.
Starter tier: till, offline_sync, tally_export.
Growth tier: + e_invoice, analytics.
"""

import uuid
import hmac
import hashlib
import time
from datetime import datetime, timedelta

from django.db import models
from django.conf import settings


class StoreLicence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store_id = models.CharField(max_length=20, unique=True)
    tier = models.CharField(max_length=20, default="starter")  # starter, growth
    features = models.JSONField(default=list)  # ["till", "offline_sync", "tally_export", ...]
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    token = models.CharField(max_length=512, unique=True, editable=False)
    issued_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, blank=True)

    class Meta:
        db_table = "ayy_licence_store"


def issue_licence(store_id, tier="starter", months=12, secret_key=None):
    """Create a licence token for a store."""
    if secret_key is None:
        secret_key = getattr(settings, "LICENCE_SECRET_KEY", "dev-secret")

    valid_until = datetime.utcnow() + timedelta(days=30 * months)
    features_map = {
        "starter": ["till", "offline_sync", "tally_export"],
        "growth": ["till", "offline_sync", "tally_export", "e_invoice", "analytics", "whatsapp_crm"],
    }
    features = features_map.get(tier, ["till"])

    # Build payload string
    payload_parts = [
        store_id,
        tier,
        str(int(valid_until.timestamp())),
        ",".join(sorted(features)),
    ]
    payload_str = "|".join(payload_parts)

    # HMAC-SHA256 signature
    signature = hmac.new(
        secret_key.encode(),
        payload_str.encode(),
        hashlib.sha256,
    ).hexdigest()

    token = f"ayy-licence-{int(time.time())}.{payload_str}.{signature}"

    licence = StoreLicence.objects.create(
        store_id=store_id,
        tier=tier,
        features=features,
        valid_until=valid_until,
        token=token,
        created_by="system",
    )
    return licence


def validate_licence(token):
    """Verify a licence token."""
    secret_key = getattr(settings, "LICENCE_SECRET_KEY", "dev-secret")
    parts = token.split(".")
    if len(parts) != 3:
        return {"valid": False, "error": "Invalid token format"}

    timestamp_str, payload_str, signature = parts
    expected = hmac.new(
        secret_key.encode(),
        payload_str.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        return {"valid": False, "error": "Invalid signature"}

    # Check database
    try:
        licence = StoreLicence.objects.get(token=token, is_active=True)
        if licence.valid_until < datetime.utcnow():
            return {"valid": False, "error": "Licence expired"}
        return {
            "valid": True,
            "store_id": licence.store_id,
            "tier": licence.tier,
            "features": licence.features,
            "valid_until": licence.valid_until.isoformat(),
        }
    except StoreLicence.DoesNotExist:
        return {"valid": False, "error": "Licence not found"}
