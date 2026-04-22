"""
Licence server views — prototype.

v0.1: in-memory JWT-like token (signed with HMAC-SHA256, no third-party deps).
Phase 1: real JWT with RS256 and proper key management.
"""
from __future__ import annotations

import hmac
import json
import base64
import hashlib
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from .models import StoreLicence


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s)


def _sign_payload(header: dict, body: dict, secret: str) -> str:
    """Create a simple HMAC-SHA256 signed token. v0.1 prototype."""
    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    b = _b64url_encode(json.dumps(body, separators=(",", ":")).encode())
    sig = hmac.new(
        secret.encode(),
        f"{h}.{b}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{h}.{b}.{sig}"


def _verify_token(token: str, secret: str) -> tuple[bool, dict | None]:
    """Verify HMAC signature and return (valid, payload)."""
    parts = token.split(".")
    if len(parts) != 3:
        return False, None
    sig = hmac.new(
        secret.encode(),
        f"{parts[0]}.{parts[1]}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(sig, parts[2]):
        return False, None
    try:
        body = json.loads(_b64url_decode(parts[1]))
        return True, body
    except (json.JSONDecodeError, Exception):
        return False, None


@csrf_exempt
@require_http_methods(["POST"])
def issue_licence(request):
    """
    Issue a licence for a store. Used by the HO console to create licences.
    Body: {store_id, plan, validity_days}
    """
    data = json.loads(request.body)
    store_id = data["store_id"]
    plan = data.get("plan", "starter")
    validity_days = data.get("validity_days", 365)

    expires_at = timezone.now() + timedelta(days=validity_days)
    features = {"till": True, "offline_sync": True, "tally_export": True}
    if plan == "growth":
        features.update({"e_invoice": True, "analytics": True})

    licence, _ = StoreLicence.objects.update_or_create(
        store_id=store_id,
        defaults={"plan": plan, "expires_at": expires_at, "features": features},
    )

    secret = getattr(settings, "LICENCE_SECRET_KEY", "store-box-dev-secret")
    header = {"alg": "HS256", "typ": "JWT", "kid": "v0.1"}
    body = {
        "iss": "ayypos-ho",
        "sub": store_id,
        "plan": plan,
        "features": features,
        "exp": int(expires_at.timestamp()),
        "iat": int(timezone.now().timestamp()),
    }
    token = _sign_payload(header, body, secret)

    return JsonResponse({
        "store_id": store_id,
        "plan": plan,
        "expires_at": expires_at.isoformat(),
        "token": token,
    })


@csrf_exempt
@require_http_methods(["POST"])
def validate_licence(request):
    """
    Called by the store box on startup or when the till needs auth check.
    Body: {token}
    Returns licence status.
    """
    data = json.loads(request.body)
    token = data["token"]
    secret = getattr(settings, "LICENCE_SECRET_KEY", "store-box-dev-secret")

    valid, body = _verify_token(token, secret)
    if not valid:
        return JsonResponse({"valid": False, "reason": "invalid_signature"}, status=401)

    store_id = body.get("sub", "")
    try:
        licence = StoreLicence.objects.get(store_id=store_id, revoked_at__isnull=True)
    except StoreLicence.DoesNotExist:
        return JsonResponse({"valid": True, "reason": "licence_not_in_db", "plan": body.get("plan")})

    if not licence.is_active():
        return JsonResponse({"valid": False, "reason": "licence_expired_or_revoked"})

    return JsonResponse({
        "valid": True,
        "plan": licence.plan,
        "features": licence.features,
        "expires_at": licence.expires_at.isoformat(),
    })
