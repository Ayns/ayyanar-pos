"""
Canonical IRP error taxonomy for the e-invoice client.

The classification is what turns an ambiguous 4xx/5xx into a deterministic
client action. Every response the IRP returns must land in exactly one class.
If a new code shows up in the wild that isn't classified here, the client
treats it as SCHEMA (unknown) — operator looks at it and either adds it to
this table or maps it to an existing class.

Codes below are drawn from the publicly-documented GSTN e-Invoice API error
list (sandbox + production use the same code space). The table is intentionally
bigger than the AYY-14 floor of 10 so that the five classes each have at
least one representative and the common operator failures are covered.

Class → client action:

  TRANSIENT — retry with exponential backoff + jitter, cap at MAX_ATTEMPTS,
              then promote to DLQ as ``retry_exhausted``.
  THROTTLE  — retry honouring server hint (`Retry-After` or 30s default)
              without consuming a retry budget.
  OUTAGE    — circuit-break per-tenant for OUTAGE_COOLDOWN; inbound new
              submissions queue, no attempt fires until cooldown lifts.
  SECURITY  — attempt auth refresh once, then retry once. If second attempt
              is still SECURITY → DLQ as ``auth_failed`` and page operator.
  BUSINESS  — permanent. Never retry. Straight to DLQ for operator fix.
  SCHEMA    — permanent. Never retry. Straight to DLQ; also alerts because a
              SCHEMA failure usually means our payload builder drifted.
  DUPLICATE — treat as success: IRP already has this IRN, persist returned
              IRN/ACK if provided, else mark submission ``already_registered``.
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


# Keyed by the IRP error code string. Codes and descriptions are from the
# GSTN e-Invoice API documentation (sandbox + production share the catalogue).
TAXONOMY: dict[str, IrpError] = {
    # ---- BUSINESS (permanent, operator fix) ----
    "2150": IrpError(
        code="2150",
        description="Duplicate IRN — invoice already registered",
        error_class=ErrorClass.DUPLICATE,
        client_action="treat as success; persist any returned IRN/ACK",
    ),
    "2172": IrpError(
        code="2172",
        description="Invalid supplier GSTIN for document date",
        error_class=ErrorClass.BUSINESS,
        client_action="DLQ; operator fixes GSTIN on source invoice",
    ),
    "2176": IrpError(
        code="2176",
        description="Invalid recipient GSTIN",
        error_class=ErrorClass.BUSINESS,
        client_action="DLQ; operator fixes recipient on source invoice",
    ),
    "2182": IrpError(
        code="2182",
        description="Taxable value and rate × quantity mismatch",
        error_class=ErrorClass.BUSINESS,
        client_action="DLQ; operator reviews line item math",
    ),
    "2189": IrpError(
        code="2189",
        description="Invalid total invoice value vs line items sum",
        error_class=ErrorClass.BUSINESS,
        client_action="DLQ; operator reviews line item math",
    ),
    "2194": IrpError(
        code="2194",
        description="Document date beyond permitted back-dating window",
        error_class=ErrorClass.BUSINESS,
        client_action=(
            "DLQ; surface to HO console with 'needs credit/debit note' hint"
        ),
    ),
    "2211": IrpError(
        code="2211",
        description="Supplier GSTIN is cancelled / inactive",
        error_class=ErrorClass.BUSINESS,
        client_action="DLQ + tenant-level alert; cannot submit until ACTIVE",
    ),
    "2212": IrpError(
        code="2212",
        description="Recipient GSTIN is cancelled / inactive",
        error_class=ErrorClass.BUSINESS,
        client_action="DLQ; operator chooses to resubmit as B2C or fix party",
    ),
    "2233": IrpError(
        code="2233",
        description="HSN code not valid for supply type",
        error_class=ErrorClass.BUSINESS,
        client_action="DLQ; operator fixes HSN in product master",
    ),
    "2265": IrpError(
        code="2265",
        description="Place of supply invalid for document type",
        error_class=ErrorClass.BUSINESS,
        client_action="DLQ; operator fixes PoS / document type",
    ),
    "2283": IrpError(
        code="2283",
        description="IRN is cancelled; further actions not allowed",
        error_class=ErrorClass.BUSINESS,
        client_action="DLQ; this is an operator-initiated cancel path",
    ),
    # ---- SCHEMA (permanent, our bug) ----
    "2100": IrpError(
        code="2100",
        description="Mandatory field missing in payload",
        error_class=ErrorClass.SCHEMA,
        client_action="DLQ + page engineering; payload builder drift",
    ),
    "2119": IrpError(
        code="2119",
        description="Invalid JSON / payload format",
        error_class=ErrorClass.SCHEMA,
        client_action="DLQ + page engineering",
    ),
    # ---- SECURITY (auth refresh path) ----
    "2284": IrpError(
        code="2284",
        description="Authentication token expired",
        error_class=ErrorClass.SECURITY,
        client_action="refresh token once, retry once, then DLQ",
    ),
    "2285": IrpError(
        code="2285",
        description="Invalid authentication token",
        error_class=ErrorClass.SECURITY,
        client_action="refresh token once, retry once, then DLQ",
    ),
    # ---- THROTTLE (per-server hint) ----
    "2244": IrpError(
        code="2244",
        description="Rate limit hit for this GSTIN",
        error_class=ErrorClass.THROTTLE,
        client_action=(
            "honour Retry-After; tenant-level token bucket tightens"
        ),
    ),
    # ---- TRANSIENT (retry budget) ----
    "HTTP_500": IrpError(
        code="HTTP_500",
        description="IRP internal server error",
        error_class=ErrorClass.TRANSIENT,
        client_action="exp backoff + jitter",
    ),
    "HTTP_502": IrpError(
        code="HTTP_502",
        description="Gateway error reaching IRP upstream",
        error_class=ErrorClass.TRANSIENT,
        client_action="exp backoff + jitter",
    ),
    "HTTP_504": IrpError(
        code="HTTP_504",
        description="IRP upstream timeout",
        error_class=ErrorClass.TRANSIENT,
        client_action="exp backoff + jitter",
    ),
    "NET_TIMEOUT": IrpError(
        code="NET_TIMEOUT",
        description="Client-side read timeout",
        error_class=ErrorClass.TRANSIENT,
        client_action="exp backoff + jitter",
    ),
    "NET_CONN_RESET": IrpError(
        code="NET_CONN_RESET",
        description="TCP reset during request",
        error_class=ErrorClass.TRANSIENT,
        client_action="exp backoff + jitter",
    ),
    # ---- OUTAGE (circuit break) ----
    "HTTP_503": IrpError(
        code="HTTP_503",
        description="IRP service unavailable (scheduled or incident)",
        error_class=ErrorClass.OUTAGE,
        client_action="open circuit per tenant for OUTAGE_COOLDOWN",
    ),
    "OUTAGE_SUSTAINED": IrpError(
        code="OUTAGE_SUSTAINED",
        description="Consecutive OUTAGE responses crossed threshold",
        error_class=ErrorClass.OUTAGE,
        client_action="circuit stays open; dashboard alert fires",
    ),
}

# Convenience handles for the retry state machine.
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
