"""Deterministic Tally XML voucher generator.

Design notes:

- Output XML is byte-deterministic for a given (scenario, version) pair. That
  is the contract the golden-file fixtures rely on; if this generator ever
  emits non-deterministic output we lose the diff-as-test-failure property
  that the board signed up for.
- We emit the `<ENVELOPE>` shape Tally's HTTP-XML endpoint expects. The
  server-side parser tolerates unknown tags but rejects missing required
  tags, so the generator errs on the side of always emitting the full
  canonical set.
- GST math is exact in `Decimal`. No floats anywhere in the tax path.
- The version matrix drives every behavioural fork. We never hand-roll an
  `if version == ERP9` outside of reading `capabilities(version)`.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from xml.etree import ElementTree as ET

from .scenarios import (
    LineItem,
    Scenario,
    Tender,
    TenderKind,
    VoucherKind,
)
from .version_matrix import TallyVersion, capabilities


# -- Decimal helpers ---------------------------------------------------------

_PAISA = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(_PAISA, rounding=ROUND_HALF_UP)


def _fmt(x: Decimal) -> str:
    # Tally expects two-decimal INR; credit amounts are negative
    return f"{_q(x):.2f}"


# -- GST split ---------------------------------------------------------------

def _gst_components(line: LineItem, is_interstate: bool) -> dict[str, Decimal]:
    """Split a GST-inclusive price into base + tax components."""
    gross = _q(line.unit_price_incl_gst * line.quantity)
    rate = Decimal(line.gst_rate_bps) / Decimal(10000)
    base = _q(gross / (Decimal(1) + rate))
    tax_total = _q(gross - base)
    if is_interstate:
        return {
            "base": base, "igst": tax_total,
            "cgst": Decimal("0.00"), "sgst": Decimal("0.00"),
        }
    half = _q(tax_total / Decimal(2))
    # Keep the two halves summing to tax_total (paisa-accurate); absorb any
    # 1-paisa drift into SGST so CGST == legal half and the voucher balances.
    sgst = tax_total - half
    return {"base": base, "igst": Decimal("0.00"), "cgst": half, "sgst": sgst}


# -- Element helpers ---------------------------------------------------------

def _child(parent: ET.Element, tag: str, text: str = "") -> ET.Element:
    el = ET.SubElement(parent, tag)
    if text != "":
        el.text = text
    return el


def _list_child(parent: ET.Element, tag: str) -> ET.Element:
    return ET.SubElement(parent, f"{tag}.LIST")


def _is_credit(kind: VoucherKind) -> bool:
    return kind == VoucherKind.CREDIT_NOTE


# -- Top-level ---------------------------------------------------------------

def build_envelope(scenario: Scenario, version: TallyVersion,
                   target_company: str = "Apparel HQ") -> ET.Element:
    cap = capabilities(version)
    envelope = ET.Element("ENVELOPE")

    header = _child(envelope, "HEADER")
    _child(header, "TALLYREQUEST", "Import Data")

    if cap.requires_target_company:
        _child(header, "TARGETCOMPANY", target_company)

    body = _child(envelope, "BODY")
    importdata = _child(body, "IMPORTDATA")
    requestdesc = _child(importdata, "REQUESTDESC")
    _child(requestdesc, "REPORTNAME", "Vouchers")
    staticvars = _child(requestdesc, "STATICVARIABLES")
    _child(staticvars, "SVCURRENTCOMPANY", target_company)
    _child(staticvars, "SVEXPORTFORMAT", "$$SysName:XML")

    requestdata = _child(importdata, "REQUESTDATA")
    message = _child(requestdata, "TALLYMESSAGE")
    message.set("xmlns:UDF", "TallyUDF")
    _build_voucher(message, scenario, version)

    return envelope


def _build_voucher(parent: ET.Element, scenario: Scenario,
                   version: TallyVersion) -> None:
    cap = capabilities(version)
    voucher = _child(parent, "VOUCHER")
    voucher.set("VCHTYPE", scenario.voucher_kind.value)
    voucher.set("ACTION", "Create")

    _child(voucher, "DATE", scenario.voucher_date)
    _child(voucher, "VOUCHERTYPENAME", scenario.voucher_kind.value)
    _child(voucher, "VOUCHERNUMBER", scenario.voucher_number)

    if scenario.original_voucher_number:
        _child(voucher, "REFERENCE", scenario.original_voucher_number)

    _child(voucher, "PARTYLEDGERNAME", scenario.party_name)
    # ERP 9 also accepts <PARTYNAME>; emit it for backwards compatibility
    if version == TallyVersion.ERP_9:
        _child(voucher, "PARTYNAME", scenario.party_name)

    _child(voucher, "NARRATION", _narration_with_markdown(scenario))
    _child(voucher, "STATEOFSUPPLY", scenario.state_of_supply)

    if scenario.is_invoice or cap.credit_note_requires_isinvoice:
        _child(voucher, "ISINVOICE", "Yes" if scenario.is_invoice else "No")

    if cap.requires_gst_reg_type and scenario.party_gstin:
        _child(voucher, "GSTREGISTRATIONTYPE", "Regular")
        _child(voucher, "PARTYGSTIN", scenario.party_gstin)
    elif cap.requires_gst_reg_type:
        _child(voucher, "GSTREGISTRATIONTYPE", "Unregistered/Consumer")

    # --- inventory (per-line) ---
    for line in scenario.lines:
        _emit_inventory_entry(voucher, scenario, line, version)

    # --- ledger entries: party + GST ledgers + tenders ---
    _emit_ledger_entries(voucher, scenario, version)

    # --- apparel UDFs ---
    _emit_apparel_udfs(voucher, scenario, version)


def _narration_with_markdown(scenario: Scenario) -> str:
    if scenario.markdown_reason:
        return f"[{scenario.markdown_reason}] {scenario.narration}"
    return scenario.narration


# -- Inventory ---------------------------------------------------------------

def _emit_inventory_entry(voucher: ET.Element, scenario: Scenario,
                          line: LineItem, version: TallyVersion) -> None:
    entry = _list_child(voucher, "ALLINVENTORYENTRIES")
    _child(entry, "STOCKITEMNAME", line.description)
    _child(entry, "ISDEEMEDPOSITIVE",
           "Yes" if _is_credit(scenario.voucher_kind) else "No")
    _child(entry, "RATE", f"{_fmt(line.unit_price_incl_gst)}/Nos")
    _child(entry, "AMOUNT", _signed_amount(scenario,
                                           line.unit_price_incl_gst * line.quantity))
    _child(entry, "ACTUALQTY", f"{line.quantity} Nos")
    _child(entry, "BILLEDQTY", f"{line.quantity} Nos")

    cap = capabilities(version)
    if cap.gst_requires_hsn or line.hsn:
        _child(entry, "HSNCODE", line.hsn)
    _child(entry, "GSTOVRDNRATE", str(Decimal(line.gst_rate_bps) / Decimal(100)))


def _signed_amount(scenario: Scenario, amount: Decimal) -> str:
    sign = Decimal(-1) if _is_credit(scenario.voucher_kind) else Decimal(1)
    return _fmt(sign * amount)


# -- Ledger entries ----------------------------------------------------------

def _emit_ledger_entries(voucher: ET.Element, scenario: Scenario,
                         version: TallyVersion) -> None:
    """Emit ALLLEDGERENTRIES.LIST children that net to zero.

    Shape Tally expects:
      - one DR leg per counter-party (either party receivable for B2B, or
        tender ledgers for retail walk-in sales)
      - one CR leg per rate-bucket sales-income ledger
      - matching CR legs for output GST (CGST+SGST intra-state, IGST inter-
        state). Credit notes flip DR/CR.

    Never both party AND tenders on the same voucher — that would double-
    count the asset side and fail Prime Server's tender-sum check.
    """
    is_interstate = scenario.state_of_supply != "Karnataka"
    buckets: dict[int, dict[str, Decimal]] = {}
    for line in scenario.lines:
        comps = _gst_components(line, is_interstate)
        bucket = buckets.setdefault(line.gst_rate_bps, {
            "base": Decimal("0.00"),
            "igst": Decimal("0.00"),
            "cgst": Decimal("0.00"),
            "sgst": Decimal("0.00"),
        })
        for k, v in comps.items():
            bucket[k] = bucket[k] + v

    # Rule: B2B (GSTIN present) uses the party ledger as the counter-party
    # leg; retail walk-in (no GSTIN) uses the tender ledgers. Exactly one
    # side — never both — to keep the voucher balanced.
    use_party_as_counter = bool(scenario.party_gstin)

    if use_party_as_counter:
        party_total = sum(
            (_q(line.unit_price_incl_gst * line.quantity) for line in scenario.lines),
            Decimal("0.00"),
        )
        _emit_single_ledger(
            voucher,
            ledger_name=scenario.party_name,
            amount=party_total,
            is_party=True,
            scenario=scenario,
        )

    # Per-rate-bucket: one sales-income ledger + matching GST ledgers
    for rate_bps, comps in sorted(buckets.items()):
        rate_pct = Decimal(rate_bps) / Decimal(100)
        _emit_single_ledger(
            voucher,
            ledger_name=f"Sales {rate_pct}%",
            amount=comps["base"],
            is_party=False,
            scenario=scenario,
            is_income=True,
        )
        if is_interstate:
            _emit_single_ledger(
                voucher,
                ledger_name=f"Output IGST {rate_pct}%",
                amount=comps["igst"],
                is_party=False,
                scenario=scenario,
                is_income=True,
            )
        else:
            _emit_single_ledger(
                voucher,
                ledger_name=f"Output CGST {rate_pct/2}%",
                amount=comps["cgst"],
                is_party=False,
                scenario=scenario,
                is_income=True,
            )
            _emit_single_ledger(
                voucher,
                ledger_name=f"Output SGST {rate_pct/2}%",
                amount=comps["sgst"],
                is_party=False,
                scenario=scenario,
                is_income=True,
            )

    if not use_party_as_counter:
        for tender in scenario.tenders:
            _emit_tender_ledger(voucher, scenario, tender)


def _emit_single_ledger(voucher: ET.Element, ledger_name: str,
                        amount: Decimal, is_party: bool, scenario: Scenario,
                        is_income: bool = False) -> None:
    entry = _list_child(voucher, "ALLLEDGERENTRIES")
    _child(entry, "LEDGERNAME", ledger_name)

    # Sign rules for Tally's <ISDEEMEDPOSITIVE>:
    # - Sale: party is DR (deemed positive = No; amount positive),
    #         income/GST is CR (deemed positive = Yes; amount negative).
    # - Credit note: inverse.
    is_credit = _is_credit(scenario.voucher_kind)
    if is_party:
        deemed_positive = "No" if not is_credit else "Yes"
        sign = Decimal(1) if not is_credit else Decimal(-1)
    else:
        # Income / GST ledgers — opposite side of the party ledger
        deemed_positive = "Yes" if not is_credit else "No"
        sign = Decimal(-1) if not is_credit else Decimal(1)

    _child(entry, "ISDEEMEDPOSITIVE", deemed_positive)
    _child(entry, "AMOUNT", _fmt(sign * amount))


def _emit_tender_ledger(voucher: ET.Element, scenario: Scenario,
                        tender: Tender) -> None:
    # Tender ledgers are the contra-leg of the party ledger: for a sale the
    # party ledger is debited for the gross, then each tender ledger is
    # credited for its share. Tally balances the voucher by the sum of all
    # ALLLEDGERENTRIES lines, which is why the generator emits both sides.
    entry = _list_child(voucher, "ALLLEDGERENTRIES")
    _child(entry, "LEDGERNAME", tender.kind.value)
    is_credit = _is_credit(scenario.voucher_kind)
    # On a sale, tender is DR (asset); on a credit note / return, CR (liability drop)
    if not is_credit:
        deemed_positive = "No"
        sign = Decimal(1)
    else:
        deemed_positive = "Yes"
        sign = Decimal(-1)
    _child(entry, "ISDEEMEDPOSITIVE", deemed_positive)
    _child(entry, "AMOUNT", _fmt(sign * tender.amount))
    if tender.reference:
        _child(entry, "REFERENCE", tender.reference)


# -- Apparel UDFs ------------------------------------------------------------

def _emit_apparel_udfs(voucher: ET.Element, scenario: Scenario,
                      version: TallyVersion) -> None:
    cap = capabilities(version)
    sizes = {l.size for l in scenario.lines if l.size}
    colors = {l.color for l in scenario.lines if l.color}
    seasons = {l.season for l in scenario.lines if l.season}
    if not (sizes or colors or seasons or scenario.markdown_reason):
        return

    def _udf(tag: str, value: str) -> None:
        # Prime tightened UDF namespaces: requires TYPE attribute. ERP 9
        # accepts the bare form. We emit Prime's form when the capability
        # demands it; otherwise the looser tag.
        el = ET.SubElement(voucher, f"UDF:{tag}")
        if cap.strict_udf_namespace:
            el.set("TYPE", "String")
            el.set("ISLIST", "No")
        el.text = value

    if sizes:
        _udf("APPAREL_SIZES", ",".join(sorted(sizes)))
    if colors:
        _udf("APPAREL_COLORS", ",".join(sorted(colors)))
    if seasons:
        _udf("APPAREL_SEASONS", ",".join(sorted(seasons)))
    if scenario.markdown_reason:
        _udf("MARKDOWN_REASON", scenario.markdown_reason)


# -- Serialization -----------------------------------------------------------

def to_xml_bytes(element: ET.Element) -> bytes:
    # Deterministic serialization: ET preserves insertion order, which is all
    # we need. No pretty-printing (Tally tolerates both, but we want
    # byte-stable goldens).
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


def to_xml_str(element: ET.Element) -> str:
    return to_xml_bytes(element).decode("utf-8")


def generate(scenario: Scenario, version: TallyVersion,
             target_company: str = "Apparel HQ") -> str:
    return to_xml_str(build_envelope(scenario, version, target_company))
