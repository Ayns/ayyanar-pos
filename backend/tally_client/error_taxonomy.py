"""Tally import-response error taxonomy — production version of AYY-15 spike.

Maps Tally response codes to action classes: retry, repair, manual DLQ,
security stop, duplicate skip, or schema failure.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TallyAction(str, Enum):
    RETRY = "retry"
    REPAIR = "repair"
    MANUAL = "manual"
    SECURITY = "security"
    DUPLICATE = "duplicate"
    SCHEMA = "schema"


@dataclass(frozen=True)
class TallyError:
    code: str
    message: str
    action: TallyAction
    versions: tuple[str, ...]


ERRORS: dict[str, TallyError] = {
    "0": TallyError("0", "OK", TallyAction.RETRY, ("erp9", "prime", "prime_server")),
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
    "6401": TallyError("6401", "Invalid GSTIN", TallyAction.MANUAL,
                       ("prime", "prime_server")),
    "6402": TallyError("6402", "GST rate mismatch with HSN master",
                       TallyAction.SCHEMA, ("prime", "prime_server")),
    "6403": TallyError("6403", "HSN code missing for GST-enabled item",
                       TallyAction.SCHEMA, ("prime", "prime_server")),
    "6404": TallyError("6404", "GSTREGISTRATIONTYPE missing on party ledger",
                       TallyAction.SCHEMA, ("prime", "prime_server")),
    "7001": TallyError("7001", "Authentication required",
                       TallyAction.SECURITY, ("prime_server",)),
    "7101": TallyError("7101", "Company not open", TallyAction.SECURITY,
                       ("erp9", "prime", "prime_server")),
    "7102": TallyError("7102", "Target company mismatch", TallyAction.SECURITY,
                       ("prime_server",)),
    "T001": TallyError("T001", "Socket timeout", TallyAction.RETRY,
                       ("erp9", "prime", "prime_server")),
    "T002": TallyError("T002", "Connection refused", TallyAction.RETRY,
                       ("erp9", "prime", "prime_server")),
}


def classify(code: str) -> TallyError:
    """Return error record for a code; unknown codes map to SCHEMA."""
    return ERRORS.get(str(code),
        TallyError(str(code), f"Unknown code {code}", TallyAction.SCHEMA, ()))
