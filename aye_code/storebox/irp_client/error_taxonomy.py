"""
Canonical IRP error taxonomy for the e-invoice client.

Class -> client action:
  TRANSIENT — retry with exponential backoff + jitter
  THROTTLE  — honour server Retry-After, no budget consumed
  OUTAGE    — circuit-break per-tenant
  SECURITY  — auth refresh once, then DLQ
  BUSINESS  — permanent, DLQ for operator fix
  SCHEMA    — permanent, DLQ + engineering alert
  DUPLICATE — treat as success
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorClass(str, Enum):
    TRANSIENT = "TRANSIENT"
    THROTTLE = "THROTTLE"
    OUTAGE = "OUTAGE"
    SECURITY = "SECURITY"
    BUSINESS = "BUSINESS"
    SCHEMA = "SCHEMA"
    DUPLICATE = "DUPLICATE"


@dataclass(frozen=True)
class IrpError:
    code: str
    description: str
    error_class: ErrorClass
    client_action: str


TAXONOMY: dict[str, IrpError] = {
    # BUSINESS (permanent, operator fix)
    "2150": IrpError("2150", "Duplicate IRN — already registered", ErrorClass.DUPLICATE, "treat as success"),
    "2172": IrpError("2172", "Invalid supplier GSTIN", ErrorClass.BUSINESS, "DLQ; operator fixes GSTIN"),
    "2176": IrpError("2176", "Invalid recipient GSTIN", ErrorClass.BUSINESS, "DLQ; operator fixes recipient"),
    "2182": IrpError("2182", "Taxable value and rate mismatch", ErrorClass.BUSINESS, "DLQ; operator reviews math"),
    "2189": IrpError("2189", "Invalid total invoice value", ErrorClass.BUSINESS, "DLQ; operator reviews math"),
    "2194": IrpError("2194", "Date beyond back-dating window", ErrorClass.BUSINESS, "DLQ; credit/debit note"),
    "2211": IrpError("2211", "Supplier GSTIN inactive", ErrorClass.BUSINESS, "DLQ + tenant alert"),
    "2212": IrpError("2212", "Recipient GSTIN inactive", ErrorClass.BUSINESS, "DLQ; B2C or fix party"),
    "2233": IrpError("2233", "HSN not valid for supply type", ErrorClass.BUSINESS, "DLQ; fix HSN"),
    "2265": IrpError("2265", "Place of supply invalid", ErrorClass.BUSINESS, "DLQ; fix PoS"),
    "2283": IrpError("2283", "IRN cancelled", ErrorClass.BUSINESS, "DLQ; operator-initiated cancel"),
    # SCHEMA (permanent, our bug)
    "2100": IrpError("2100", "Mandatory field missing", ErrorClass.SCHEMA, "DLQ + page engineering"),
    "2119": IrpError("2119", "Invalid JSON / payload format", ErrorClass.SCHEMA, "DLQ + page engineering"),
    # SECURITY
    "2284": IrpError("2284", "Auth token expired", ErrorClass.SECURITY, "refresh token once, retry"),
    "2285": IrpError("2285", "Invalid auth token", ErrorClass.SECURITY, "refresh token once, retry"),
    # THROTTLE
    "2244": IrpError("2244", "Rate limit hit", ErrorClass.THROTTLE, "honour Retry-After"),
    # TRANSIENT
    "HTTP_500": IrpError("HTTP_500", "IRP internal server error", ErrorClass.TRANSIENT, "exp backoff + jitter"),
    "HTTP_502": IrpError("HTTP_502", "Gateway error", ErrorClass.TRANSIENT, "exp backoff + jitter"),
    "HTTP_504": IrpError("HTTP_504", "IRP upstream timeout", ErrorClass.TRANSIENT, "exp backoff + jitter"),
    "NET_TIMEOUT": IrpError("NET_TIMEOUT", "Client read timeout", ErrorClass.TRANSIENT, "exp backoff + jitter"),
    "NET_CONN_RESET": IrpError("NET_CONN_RESET", "TCP reset", ErrorClass.TRANSIENT, "exp backoff + jitter"),
    # OUTAGE
    "HTTP_503": IrpError("HTTP_503", "IRP service unavailable", ErrorClass.OUTAGE, "circuit break per tenant"),
    "OUTAGE_SUSTAINED": IrpError("OUTAGE_SUSTAINED", "Consecutive OUTAGE responses", ErrorClass.OUTAGE, "circuit stays open"),
}

TRANSIENT_CODES = {c for c, e in TAXONOMY.items() if e.error_class == ErrorClass.TRANSIENT}
THROTTLE_CODES = {c for c, e in TAXONOMY.items() if e.error_class == ErrorClass.THROTTLE}
OUTAGE_CODES = {c for c, e in TAXONOMY.items() if e.error_class == ErrorClass.OUTAGE}
SECURITY_CODES = {c for c, e in TAXONOMY.items() if e.error_class == ErrorClass.SECURITY}
BUSINESS_CODES = {c for c, e in TAXONOMY.items() if e.error_class == ErrorClass.BUSINESS}
SCHEMA_CODES = {c for c, e in TAXONOMY.items() if e.error_class == ErrorClass.SCHEMA}
DUPLICATE_CODES = {c for c, e in TAXONOMY.items() if e.error_class == ErrorClass.DUPLICATE}


def classify(code: str) -> ErrorClass:
    """Return the class for a known code; unknown codes map to SCHEMA."""
    entry = TAXONOMY.get(code)
    if entry is None:
        return ErrorClass.SCHEMA
    return entry.error_class
