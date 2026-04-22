"""The eight daily-sales voucher scenarios.

Each scenario is a pure data object (no XML). The generator in xml_generator
turns these into version-specific Tally XML payloads.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class VoucherKind(str, Enum):
    SALE = "Sales"
    CREDIT_NOTE = "Credit Note"


class TenderKind(str, Enum):
    CASH = "Cash"
    UPI = "UPI Receivable"
    CARD = "Card Receivable"
    STORE_CREDIT = "Store Credit"


@dataclass(frozen=True)
class LineItem:
    sku: str
    description: str
    hsn: str
    quantity: Decimal
    mrp: Decimal
    unit_price_incl_gst: Decimal
    gst_rate_bps: int
    size: str = ""
    color: str = ""
    season: str = ""


@dataclass(frozen=True)
class Tender:
    kind: TenderKind
    amount: Decimal
    reference: str = ""


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    voucher_kind: VoucherKind
    voucher_number: str
    voucher_date: str
    party_name: str
    party_gstin: str
    state_of_supply: str
    narration: str
    lines: tuple[LineItem, ...]
    tenders: tuple[Tender, ...]
    original_voucher_number: str = ""
    is_invoice: bool = True
    markdown_reason: str = ""


def cash_sale() -> Scenario:
    return Scenario(
        scenario_id="cash_sale", voucher_kind=VoucherKind.SALE,
        voucher_number="AP-1001", voucher_date="20260420",
        party_name="Walk-in Customer", party_gstin="",
        state_of_supply="Karnataka", narration="Counter sale, cash tender",
        lines=(LineItem(sku="SH-BLU-M", description="Blue Shirt M", hsn="6205",
                        quantity=Decimal("1"), mrp=Decimal("1499.00"),
                        unit_price_incl_gst=Decimal("1499.00"),
                        gst_rate_bps=500, size="M", color="Blue", season="SS26"),),
        tenders=(Tender(kind=TenderKind.CASH, amount=Decimal("1499.00")),),
    )


def upi_sale() -> Scenario:
    return Scenario(
        scenario_id="upi_sale", voucher_kind=VoucherKind.SALE,
        voucher_number="AP-1002", voucher_date="20260420",
        party_name="Walk-in Customer", party_gstin="",
        state_of_supply="Karnataka", narration="Counter sale, UPI tender",
        lines=(LineItem(sku="TR-BLK-32", description="Black Trousers 32", hsn="6203",
                        quantity=Decimal("1"), mrp=Decimal("2299.00"),
                        unit_price_incl_gst=Decimal("2299.00"),
                        gst_rate_bps=1200, size="32", color="Black", season="SS26"),),
        tenders=(Tender(kind=TenderKind.UPI, amount=Decimal("2299.00"),
                        reference="UPI-RRN-4480012"),),
    )


def mixed_tender_sale() -> Scenario:
    return Scenario(
        scenario_id="mixed_tender_sale", voucher_kind=VoucherKind.SALE,
        voucher_number="AP-1003", voucher_date="20260420",
        party_name="Walk-in Customer", party_gstin="",
        state_of_supply="Karnataka", narration="Counter sale, split cash + UPI + card",
        lines=(
            LineItem(sku="SH-WHT-L", description="White Shirt L", hsn="6205",
                     quantity=Decimal("1"), mrp=Decimal("1799.00"),
                     unit_price_incl_gst=Decimal("1799.00"),
                     gst_rate_bps=500, size="L", color="White", season="SS26"),
            LineItem(sku="TR-BLU-34", description="Blue Trousers 34", hsn="6203",
                     quantity=Decimal("1"), mrp=Decimal("2499.00"),
                     unit_price_incl_gst=Decimal("2499.00"),
                     gst_rate_bps=1200, size="34", color="Blue", season="SS26"),
        ),
        tenders=(
            Tender(kind=TenderKind.CASH, amount=Decimal("500.00")),
            Tender(kind=TenderKind.UPI, amount=Decimal("1500.00"), reference="UPI-RRN-4480013"),
            Tender(kind=TenderKind.CARD, amount=Decimal("2298.00"), reference="PINE-987654"),
        ),
    )


def return_sale() -> Scenario:
    return Scenario(
        scenario_id="return_sale", voucher_kind=VoucherKind.CREDIT_NOTE,
        voucher_number="CN-1001", voucher_date="20260420",
        party_name="Walk-in Customer", party_gstin="",
        state_of_supply="Karnataka", narration="Return against AP-1001",
        lines=(LineItem(sku="SH-BLU-M", description="Blue Shirt M", hsn="6205",
                        quantity=Decimal("1"), mrp=Decimal("1499.00"),
                        unit_price_incl_gst=Decimal("1499.00"),
                        gst_rate_bps=500, size="M", color="Blue", season="SS26"),),
        tenders=(Tender(kind=TenderKind.CASH, amount=Decimal("1499.00")),),
        original_voucher_number="AP-1001",
    )


def exchange_sale() -> Scenario:
    return Scenario(
        scenario_id="exchange_sale", voucher_kind=VoucherKind.SALE,
        voucher_number="AP-1004", voucher_date="20260420",
        party_name="Walk-in Customer", party_gstin="",
        state_of_supply="Karnataka", narration="Exchange: return SH-BLU-M, new SH-BLU-L",
        lines=(LineItem(sku="SH-BLU-L", description="Blue Shirt L", hsn="6205",
                        quantity=Decimal("1"), mrp=Decimal("1599.00"),
                        unit_price_incl_gst=Decimal("1599.00"),
                        gst_rate_bps=500, size="L", color="Blue", season="SS26"),),
        tenders=(
            Tender(kind=TenderKind.STORE_CREDIT, amount=Decimal("1499.00"), reference="EXCH-AP-1001"),
            Tender(kind=TenderKind.CASH, amount=Decimal("100.00")),
        ),
        original_voucher_number="AP-1001",
    )


def gst_credit_note() -> Scenario:
    return Scenario(
        scenario_id="gst_credit_note", voucher_kind=VoucherKind.CREDIT_NOTE,
        voucher_number="CN-1002", voucher_date="20260420",
        party_name="Acme Retail Pvt Ltd", party_gstin="29ABCDE1234F1Z5",
        state_of_supply="Karnataka", narration="Credit note against B2B invoice AP-1005",
        lines=(LineItem(sku="JK-GRN-XL", description="Green Jacket XL", hsn="6201",
                        quantity=Decimal("2"), mrp=Decimal("4999.00"),
                        unit_price_incl_gst=Decimal("4999.00"),
                        gst_rate_bps=1200, size="XL", color="Green", season="AW26"),),
        tenders=(Tender(kind=TenderKind.STORE_CREDIT, amount=Decimal("9998.00"),
                        reference="CN-AGAINST-AP-1005"),),
        original_voucher_number="AP-1005",
    )


def multi_line_mixed_gst() -> Scenario:
    return Scenario(
        scenario_id="multi_line_mixed_gst", voucher_kind=VoucherKind.SALE,
        voucher_number="AP-1006", voucher_date="20260420",
        party_name="Walk-in Customer", party_gstin="",
        state_of_supply="Karnataka", narration="Multi-line invoice, mixed GST slabs (5/12/18)",
        lines=(
            LineItem(sku="SH-BLU-M", description="Blue Shirt M", hsn="6205",
                     quantity=Decimal("2"), mrp=Decimal("999.00"),
                     unit_price_incl_gst=Decimal("999.00"),
                     gst_rate_bps=500, size="M", color="Blue", season="SS26"),
            LineItem(sku="JK-GRN-L", description="Green Jacket L", hsn="6201",
                     quantity=Decimal("1"), mrp=Decimal("3499.00"),
                     unit_price_incl_gst=Decimal("3499.00"),
                     gst_rate_bps=1200, size="L", color="Green", season="AW26"),
            LineItem(sku="AC-BAG-STD", description="Leather Bag", hsn="4202",
                     quantity=Decimal("1"), mrp=Decimal("5999.00"),
                     unit_price_incl_gst=Decimal("5999.00"),
                     gst_rate_bps=1800, size="", color="Brown", season="AW26"),
        ),
        tenders=(Tender(kind=TenderKind.CARD, amount=Decimal("11496.00"),
                        reference="PINE-987655"),),
    )


def manual_markdown_sale() -> Scenario:
    return Scenario(
        scenario_id="manual_markdown_sale", voucher_kind=VoucherKind.SALE,
        voucher_number="AP-1007", voucher_date="20260420",
        party_name="Walk-in Customer", party_gstin="",
        state_of_supply="Karnataka",
        narration="Manual markdown applied (store manager override)",
        lines=(LineItem(sku="SH-WHT-M", description="White Shirt M", hsn="6205",
                        quantity=Decimal("1"), mrp=Decimal("1799.00"),
                        unit_price_incl_gst=Decimal("1349.25"),
                        gst_rate_bps=500, size="M", color="White", season="SS26"),),
        tenders=(Tender(kind=TenderKind.CASH, amount=Decimal("1349.25")),),
        markdown_reason="MANAGER-OVERRIDE: clearance",
    )


ALL_SCENARIOS: tuple[Scenario, ...] = (
    cash_sale(), upi_sale(), mixed_tender_sale(), return_sale(),
    exchange_sale(), gst_credit_note(), multi_line_mixed_gst(), manual_markdown_sale(),
)


def scenarios_by_id() -> dict[str, Scenario]:
    return {s.scenario_id: s for s in ALL_SCENARIOS}
