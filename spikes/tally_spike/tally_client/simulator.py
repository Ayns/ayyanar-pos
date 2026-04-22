"""In-process Tally HTTP-XML simulator.

Why a simulator (and not only real Tally): the spike's hermetic test suite
must be runnable in CI with zero Windows licences. The simulator replays
the documented Tally import-response grammar for each version, including
the codes that version actually emits (see `error_taxonomy`). When Phase 1
stands up real Tally VMs, the simulator stays the authority for schema-level
assertions and real Tally adds empirical latency / race-condition coverage.

Schema-level behaviour implemented:

- Parse envelope, reject if missing required header / body children.
- Version-specific validations (TARGETCOMPANY for Prime Server, GSTIN format
  for Prime, HSN requirement, GSTREGISTRATIONTYPE requirement).
- Tender-sum check enabled for Prime Server.
- Duplicate detection keyed on (voucher_type, voucher_number) with an
  in-process ledger.
- Successful imports produce a round-trippable `<TALLYMESSAGE>` export in
  the response, suitable for the day-book back-out equivalence test.

Behaviour deliberately NOT implemented (covered by the real-VM Phase 1
extension only):

- Latency distribution / throttle / outage.
- Concurrent voucher numbering conflicts under parallel import.
- Cross-voucher stock adjustments (we treat stock masters as pre-seeded).
- Network-level failures (`T001`, `T002`) — that's the retry-client's job
  to simulate, not Tally's.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from .error_taxonomy import ERRORS, TallyError, classify
from .version_matrix import TallyVersion, capabilities


# Matches the 15-char GSTIN pattern (2 digits state + 10 PAN + 1 entity + Z + 1 check)
_GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


@dataclass
class ImportResult:
    code: str
    message: str
    created: int
    ignored: int
    round_trip_xml: str = ""

    @property
    def ok(self) -> bool:
        return self.code == "0"

    @property
    def error(self) -> TallyError:
        return classify(self.code)


@dataclass
class _State:
    # Keyed by (vchtype, voucher_number). Holds the imported envelope bytes
    # so we can reproduce Tally's XML export back-out.
    imported: dict[tuple[str, str], bytes] = field(default_factory=dict)


class TallySimulator:
    """One simulator instance per test (kept stateless across versions by
    default so tests don't leak between cases).
    """

    def __init__(self, version: TallyVersion,
                 target_company: str = "Apparel HQ") -> None:
        self.version = version
        self.target_company = target_company
        self._state = _State()

    # --- public API ---------------------------------------------------------

    def post(self, xml: str) -> ImportResult:
        try:
            envelope = ET.fromstring(xml)
        except ET.ParseError as exc:
            return _schema_err("6402", f"Malformed XML: {exc}")
        cap = capabilities(self.version)

        header = envelope.find("HEADER")
        body = envelope.find("BODY")
        if header is None or body is None:
            return _schema_err("6402", "Envelope missing HEADER or BODY")

        if cap.requires_target_company:
            tc = header.find("TARGETCOMPANY")
            if tc is None or (tc.text or "").strip() != self.target_company:
                return _sec_err("7102", "Target company mismatch")

        tallymsg = envelope.find(".//TALLYMESSAGE")
        voucher = tallymsg.find("VOUCHER") if tallymsg is not None else None
        if voucher is None:
            return _schema_err("6402", "TALLYMESSAGE missing VOUCHER")

        # Per-voucher validation ------------------------------------------------
        vchtype = voucher.get("VCHTYPE", "")
        vnumber = _text(voucher, "VOUCHERNUMBER")
        if not vchtype or not vnumber:
            return _schema_err("6402", "Voucher missing VCHTYPE or VOUCHERNUMBER")

        key = (vchtype, vnumber)
        if key in self._state.imported:
            return ImportResult(
                code="6210",
                message="Duplicate voucher number",
                created=0, ignored=1,
            )

        err = self._validate_gst(voucher, cap)
        if err:
            return err
        err = self._validate_hsn(voucher, cap)
        if err:
            return err
        err = self._validate_tender_sum(voucher, cap)
        if err:
            return err
        err = self._validate_gst_reg_type(voucher, cap)
        if err:
            return err

        # Accept.
        payload = ET.tostring(envelope, encoding="utf-8", xml_declaration=True)
        self._state.imported[key] = payload
        return ImportResult(
            code="0", message="OK", created=1, ignored=0,
            round_trip_xml=self._export_voucher_back(voucher),
        )

    def export_voucher(self, vchtype: str, voucher_number: str) -> str:
        """Simulates Tally's Day Book XML export for a single voucher."""
        payload = self._state.imported.get((vchtype, voucher_number))
        if not payload:
            return ""
        root = ET.fromstring(payload)
        tallymsg = root.find(".//TALLYMESSAGE")
        return ET.tostring(tallymsg, encoding="unicode") if tallymsg is not None else ""

    # --- validators ---------------------------------------------------------

    def _validate_gst(self, voucher: ET.Element, cap) -> ImportResult | None:
        gstin = _text(voucher, "PARTYGSTIN")
        if gstin and cap.version in (TallyVersion.PRIME, TallyVersion.PRIME_SERVER):
            if not _GSTIN_RE.match(gstin):
                return _manual_err("6401", f"Invalid GSTIN: {gstin}")
        return None

    def _validate_hsn(self, voucher: ET.Element, cap) -> ImportResult | None:
        if not cap.gst_requires_hsn:
            return None
        for inv in voucher.findall("ALLINVENTORYENTRIES.LIST"):
            hsn = _text(inv, "HSNCODE")
            if not hsn:
                item = _text(inv, "STOCKITEMNAME")
                return _schema_err(
                    "6403", f"HSN code missing for GST-enabled item: {item}",
                )
        return None

    def _validate_tender_sum(self, voucher: ET.Element, cap) -> ImportResult | None:
        if not cap.strict_tender_sum_check:
            return None
        # Sum of ALLLEDGERENTRIES must net to zero within ±0.01 INR
        from decimal import Decimal
        total = Decimal("0.00")
        for le in voucher.findall("ALLLEDGERENTRIES.LIST"):
            amt = _text(le, "AMOUNT") or "0"
            try:
                total += Decimal(amt)
            except Exception:
                return _schema_err("6402", f"Non-decimal AMOUNT: {amt}")
        if abs(total) > Decimal("0.01"):
            return _schema_err(
                "6212",
                f"Tender total does not balance with invoice (drift={total})",
            )
        return None

    def _validate_gst_reg_type(self, voucher: ET.Element, cap) -> ImportResult | None:
        if not cap.requires_gst_reg_type:
            return None
        if _text(voucher, "GSTREGISTRATIONTYPE") == "":
            return _schema_err(
                "6404", "GSTREGISTRATIONTYPE missing on party ledger",
            )
        return None

    # --- export back-out ----------------------------------------------------

    def _export_voucher_back(self, voucher: ET.Element) -> str:
        """Produce the XML shape Tally's Day Book export emits.

        The shape of the exported XML is what the `round_trip` test consumes.
        Real Tally returns a trimmed voucher envelope without the IMPORTDATA
        wrapper, so we mimic that.
        """
        out = ET.Element("TALLYMESSAGE")
        out.set("xmlns:UDF", "TallyUDF")
        # Keep the original element order but re-root under TALLYMESSAGE.
        out.append(voucher)
        return ET.tostring(out, encoding="unicode")


# -- module helpers ----------------------------------------------------------

def _text(parent: ET.Element, tag: str) -> str:
    el = parent.find(tag)
    if el is None or el.text is None:
        return ""
    return el.text.strip()


def _schema_err(code: str, msg: str) -> ImportResult:
    return ImportResult(code=code, message=msg, created=0, ignored=1)


def _manual_err(code: str, msg: str) -> ImportResult:
    return ImportResult(code=code, message=msg, created=0, ignored=1)


def _sec_err(code: str, msg: str) -> ImportResult:
    return ImportResult(code=code, message=msg, created=0, ignored=1)


# Re-export for convenience
__all__ = [
    "ImportResult",
    "TallySimulator",
    "ERRORS",
]
