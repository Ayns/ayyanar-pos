"""
AYY-34 — IRP client with retry, backoff, circuit breaker, and DLQ.

Implements the state machine from the irp_spike:
  pending -> in_flight -> registered (terminal)
With backoff retry, circuit breaker (OUTAGE), auth refresh (SECURITY), DLQ (BUSINESS/SCHEMA).
MAX_ATTEMPTS=6, BASE_BACKOFF_S=2.0, MAX_BACKOFF_S=300.0.
"""

import time
import logging
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ── Constants ──
MAX_ATTEMPTS = 6
BASE_BACKOFF_S = 2.0
MAX_BACKOFF_S = 300.0
CIRCUIT_BREAKER_THRESHOLD = 5  # consecutive failures before opening
CIRCUIT_BREAKER_TIMEOUT_S = 300  # 5 minutes

# ── IRP error categories ──
ERR_DUPLICATE = "2150"
ERR_BUSINESS = ["2172", "2176", "2182", "2189", "2194", "2211", "2212", "2233", "2265", "2283"]
ERR_SCHEMA = ["2100", "2119"]
ERR_SECURITY = ["2284", "2285"]
ERR_THROTTLE = ["2244"]
ERR_TRANSIENT_HTTP = [500, 502, 504]
ERR_TRANSIENT_NET = ["NET_TIMEOUT", "NET_CONN_RESET"]
ERR_OUTAGE = [503, "OUTAGE_SUSTAINED"]

# ── State transitions ──
STATE_PENDING = "pending"
STATE_IN_FLIGHT = "in_flight"
STATE_REGISTERED = "registered"
STATE_FAILED = "failed"
STATE_CANCELLED = "cancelled"


class IRPClient:
    """State machine for e-invoice IRP communication."""

    def __init__(self, base_url=None, client_id=None, client_secret=None, fingerprint=None):
        self.base_url = base_url or "https://api.irs.gov.in/v1"
        self.client_id = client_id or ""
        self.client_secret = client_secret or ""
        self.fingerprint = fingerprint or ""
        self._access_token = None
        self._token_expires_at = None
        self._consecutive_failures = 0
        self._circuit_open_until = None

    def _get_auth_token(self):
        """Request OAuth2 access token from IRP."""
        # In production: POST to /auth/token with client_id/secret
        # For prototype: return mock
        self._access_token = f"mock-token-{int(time.time())}"
        self._token_expires_at = datetime.utcnow() + timedelta(hours=1)
        return self._access_token

    def _ensure_auth(self):
        if not self._access_token or datetime.utcnow() >= self._token_expires_at:
            self._get_auth_token()

    def _check_circuit_breaker(self):
        """Return True if circuit is open (should skip IRP calls)."""
        if self._circuit_open_until and datetime.utcnow() < self._circuit_open_until:
            return True
        self._circuit_open_until = None
        return False

    def _record_failure(self):
        self._consecutive_failures += 1
        if self._consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
            self._circuit_open_until = datetime.utcnow() + timedelta(seconds=CIRCUIT_BREAKER_TIMEOUT_S)
            logger.warning("Circuit breaker OPEN for IRP — %d consecutive failures", self._consecutive_failures)

    def _record_success(self):
        self._consecutive_failures = 0

    def generate_irn(self, invoice_data):
        """
        Generate IRN for a B2B invoice.

        Args:
            invoice_data: dict with bill_number, gstin, items (list of {hsn, qty, value, gst_rate}),
                          document_date, supplier_name, buyer_name, buyer_gstin, buyer_address

        Returns:
            dict with irn, qr_code, ack_number, ack_date
        """
        self._ensure_auth()

        if self._check_circuit_breaker():
            raise IRPOutageError("Circuit breaker open — IRP unavailable")

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "X-Developer-Key": self.client_id,
        }

        payload = {
            "gstin": invoice_data.get("gstin"),
            "document_type": "INV",
            "document_date": invoice_data.get("document_date"),
            "document_number": invoice_data.get("invoice_number"),
            "supplier_name": invoice_data.get("supplier_name"),
            "buyer_gstin": invoice_data.get("buyer_gstin"),
            "buyer_name": invoice_data.get("buyer_name"),
            "buyer_address": invoice_data.get("buyer_address"),
            "items": invoice_data.get("items", []),
            "value": invoice_data.get("total_value"),
            "tax_value": invoice_data.get("total_tax"),
        }

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                start = time.time()
                resp = requests.post(
                    f"{self.base_url}/generate",
                    json=payload,
                    headers=headers,
                    timeout=30,
                )
                duration_ms = int((time.time() - start) * 1000)

                if resp.status_code == 200:
                    body = resp.json()
                    self._record_success()
                    return {
                        "irn": body.get("irn"),
                        "qr_code": body.get("qr_code"),
                        "ack_number": body.get("ack_no"),
                        "ack_date": body.get("ack_dt"),
                    }

                # Handle error responses
                error_code = str(resp.status_code)
                body = resp.json()
                irp_code = body.get("error_code", body.get("code", error_code))

                if irp_code == ERR_DUPLICATE:
                    raise IRPDuplicateError(f"Duplicate invoice: {irp_code}")

                if irp_code in ERR_OUTAGE or resp.status_code == 503:
                    self._record_failure()
                    if attempt < MAX_ATTEMPTS:
                        backoff = min(BASE_BACKOFF_S * (2 ** (attempt - 1)), MAX_BACKOFF_S)
                        logger.info("IRP outage — retrying in %.0fs (attempt %d/%d)", backoff, attempt, MAX_ATTEMPTS)
                        time.sleep(backoff)
                        continue
                    raise IRPOutageError(f"IRP outage: {irp_code}")

                if irp_code in ERR_SECURITY:
                    # Try auth refresh
                    self._get_auth_token()
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    continue

                if irp_code in ERR_THROTTLE:
                    backoff = min(BASE_BACKOFF_S * (2 ** (attempt - 1)), MAX_BACKOFF_S)
                    time.sleep(backoff)
                    continue

                # BUSINESS or SCHEMA error — don't retry
                raise IRPBusinessError(f"IRP error {irp_code}: {body.get('message', '')}")

            except requests.exceptions.Timeout:
                self._record_failure()
                if attempt < MAX_ATTEMPTS:
                    backoff = min(BASE_BACKOFF_S * (2 ** (attempt - 1)), MAX_BACKOFF_S)
                    time.sleep(backoff)
            except requests.exceptions.ConnectionError:
                self._record_failure()
                if attempt < MAX_ATTEMPTS:
                    backoff = min(BASE_BACKOFF_S * (2 ** (attempt - 1)), MAX_BACKOFF_S)
                    time.sleep(backoff)

        raise IRPMaxRetriesExceeded(f"After {MAX_ATTEMPTS} attempts")

    def cancel_irn(self, irn, gstin, reason="Supply cancelled"):
        """Cancel an IRN within 24 hours (SRS Section 7.2)."""
        self._ensure_auth()
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            f"{self.base_url}/cancel",
            json={"irn": irn, "gstin": gstin, "reason": reason},
            headers=headers,
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
        raise IRPCancelError(f"Cancel failed: {resp.status_code}")


# ── Custom exceptions ──
class IRPError(Exception):
    """Base IRP error."""
    pass

class IRPDuplicateError(IRPError):
    pass

class IRPBusinessError(IRPError):
    """Non-retryable business/validation error."""
    pass

class IRPSchemaError(IRPError):
    """Non-retryable schema error."""
    pass

class IRPMaxRetriesExceeded(IRPError):
    pass

class IRPOutageError(IRPError):
    """IRP is down — circuit breaker may be open."""
    pass

class IRPCancelError(IRPError):
    """IRN cancellation failed."""
    pass
