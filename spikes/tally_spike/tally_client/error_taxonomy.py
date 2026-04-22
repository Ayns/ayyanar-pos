"""Tally import-response error taxonomy.

Tally returns structured `<LINEERROR>` entries (ERP 9) or numeric error codes
inside `<RESPONSE>` blocks (Prime / Prime Server). Both shapes collapse into
a code + human message. This table is the canonical classification our
client uses to decide: retry, repair-and-retry, or send to manual-fix DLQ.

The action classes mirror the IRP client's shape on purpose — the operator
runbook on top of these is shared between the two integrations.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TallyAction(str, Enum):
    RETRY = "retry"                  # transient; safe to retry as-is
    REPAIR = "repair"                # fixable server-side (missing master); open a repair job
    MANUAL = "manual"                # business error; operator must reconcile
    SECURITY = "security"            # auth / routing; stop and page
    DUPLICATE = "duplicate"          # already imported; treat as idempotent success
    SCHEMA = "schema"                # our bug; payload malformed; never retry


@dataclass(frozen=True)
class TallyError:
    code: str
    message: str
    action: TallyAction
    # Which Tally surfaces emit this code; used by the simulator to stay
    # faithful to version-specific behaviour.
    versions: tuple[str, ...]


ERRORS: dict[str, TallyError] = {
    "0": TallyError("0", "OK", TallyAction.RETRY, ("erp9", "prime", "prime_server")),

    # 6xxx — voucher / master domain
    "6201": TallyError("6201", "Ledger does not exist", TallyAction.REPAIR,
                       ("erp9", "prime", "prime_server")),
    "6203": TallyError("6203", "Voucher date out of financial period",
                       TallyAction.MANUAL, ("erp9", "prime", "prime_server")),
    "6210": TallyError("6210", "Duplicate voucher number",
                       TallyAction.DUPLICATE, ("erp9", "prime", "prime_server")),
    "6211": TallyError("6211", "Stock item not found", TallyAction.REPAIR,
                       ("erp9", "prime", "prime_server")),
    "6212": TallyError("6212", "Tender total does not balance with invoice",
                       TallyAction.SCHEMA, ("prime_server",)),
    "6213": TallyError("6213", "Voucher type not found",
                       TallyAction.REPAIR, ("erp9", "prime", "prime_server")),

    # 64xx — GST
    "6401": TallyError("6401", "Invalid GSTIN", TallyAction.MANUAL,
                       ("prime", "prime_server")),
    "6402": TallyError("6402", "GST rate mismatch with HSN master",
                       TallyAction.SCHEMA, ("prime", "prime_server")),
    "6403": TallyError("6403", "HSN code missing for GST-enabled item",
                       TallyAction.SCHEMA, ("prime", "prime_server")),
    "6404": TallyError("6404", "GSTREGISTRATIONTYPE missing on party ledger",
                       TallyAction.SCHEMA, ("prime", "prime_server")),

    # 7xxx — server / routing (Prime Server only, mostly)
    "7001": TallyError("7001", "Authentication required",
                       TallyAction.SECURITY, ("prime_server",)),
    "7101": TallyError("7101", "Company not open", TallyAction.SECURITY,
                       ("erp9", "prime", "prime_server")),
    "7102": TallyError("7102", "Target company mismatch", TallyAction.SECURITY,
                       ("prime_server",)),

    # Transport-level (wrapped by the client, not returned by Tally itself)
    "T001": TallyError("T001", "Socket timeout", TallyAction.RETRY,
                       ("erp9", "prime", "prime_server")),
    "T002": TallyError("T002", "Connection refused (Tally not running)",
                       TallyAction.RETRY, ("erp9", "prime", "prime_server")),
}


def classify(code: str) -> TallyError:
    """Return the error record for a code, falling back to SCHEMA for unknown.

    Unknown codes land on SCHEMA (treat as our bug) on purpose: if Tally emits
    something we haven't classified, we must never auto-retry it blindly.
    """
    return ERRORS.get(
        str(code),
        TallyError(str(code), f"Unknown code {code}", TallyAction.SCHEMA, ()),
    )


def codes_for_version(version_key: str) -> tuple[str, ...]:
    return tuple(c for c, e in ERRORS.items() if version_key in e.versions)
