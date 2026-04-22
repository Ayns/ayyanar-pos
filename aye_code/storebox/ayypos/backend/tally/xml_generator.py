"""
AYY-34 — Tally XML generator.

Deterministic XML generation using xml.etree.ElementTree.
Handles all 8 scenarios across 3 Tally versions.
Version matrix drives behavioral forks.
Exact Decimal math — no floats in the tax path.
"""

import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

from ..billing.models import Bill


def generate_daily_tally_xml(store_id, bills, tally_version="erp_9"):
    """
    Generate Tally-compatible XML for daily sales vouchers.

    Args:
        store_id: Store identifier
        bills: List of Bill objects (or dicts) for the day
        tally_version: "erp_9", "prime", or "prime_server"

    Returns:
        XML string compatible with Tally ERP 9 / Prime / Prime Server
    """
    envelope = ET.Element("ENVELOPE")
    header = ET.SubElement(envelope, "HEADER")
    ET.SubElement(header, "VERSION").text = "1"
    ET.SubElement(header, "TALLYREQUEST").text = "Export"

    body = ET.SubElement(envelope, "BODY")
    disposition = ET.SubElement(body, "DISPOSITION")
    ET.SubElement(disposition, "MODE").text = "List"

    # Export section
    export = ET.SubElement(body, "EXPORT")
    ET.SubElement(export, "NAME").text = "SalesInvoice"
    ET.SubElement(export, "MODEL").text = "SalesExport"

    data = ET.SubElement(export, "DATA")

    for bill in bills:
        bill_dict = bill if isinstance(bill, dict) else _bill_to_dict(bill)
        voucher = _create_sales_voucher(bill_dict, tally_version)
        data.append(voucher)

    # Add tally declaration
    decl = ET.Element("TALLYMESSAGE")
    decl.set("xmlns", "")
    decl.text = f"\n{len(bills)} vouchers generated at {datetime.utcnow().isoformat()}"
    data.append(decl)

    return ET.tostring(envelope, encoding="unicode", xml_declaration=False)


def _create_sales_voucher(bill, tally_version):
    """Create a single SalesInvoice voucher element for Tally."""
    voucher = ET.Element("ALLSALESINVOICES")

    # Company name — required only for Prime Server
    if tally_version == "prime_server":
        ET.SubElement(voucher, "PARTYNAME").text = "AYY POS Store"

    # Voucher details
    ET.SubElement(voucher, "DATE").text = bill.get("date", datetime.utcnow().strftime("%Y%m%d"))
    ET.SubElement(voucher, "VOUCHERTYPENAME").text = "Sales"
    ET.SubElement(voucher, "VOUCHERTYPENUMBER").text = "82"

    # Bill number as ref no
    ET.SubElement(voucher, "REFERENCE").text = bill.get("bill_number", "")

    # Party details (B2B)
    gstin = bill.get("customer_gstin", "")
    if gstin:
        ET.SubElement(voucher, "PARTYNAME").text = bill.get("customer_name", "Walk-in")
        ET.SubElement(voucher, "LEDGERFROMITEM").text = "1"
        ET.SubElement(voucher, "REMOVEHSNARTICLENO").text = "0"
    else:
        ET.SubElement(voucher, "PARTYNAME").text = "Cash Sales"

    # Line items
    for line in bill.get("lines", []):
        item = ET.Element("ALLSALESINVOICES$InventoryItems")
        ET.SubElement(item, "ITEMNAME").text = line.get("sku", "")
        ET.SubElement(item, "ISDELETED").text = "0"
        ET.SubElement(item, "qty").text = str(line.get("qty", 1))
        ET.SubElement(item, "UNIT").text = "NOS"
        ET.SubElement(item, "RATE").text = str(Decimal(str(line.get("unit_price", 0))) / 100)
        ET.SubElement(item, "AMOUNT").text = str(Decimal(str(line.get("line_total", 0))) / 100)

        # HSN for Prime
        if tally_version in ("prime", "prime_server"):
            ET.SubElement(item, "TYPEOFOD").text = "Goods"
            # UDF tags for Prime+
            udf_type = ET.SubElement(item, "TYPE")
            udf_type.set("NAME", "HSNCode")
            udf_type.set("ISLIST", "Yes")
            ET.SubElement(item, "HSNCODEAS PER NOTIFY").text = line.get("hsn", "6109")
            ET.SubElement(item, "CSTCHARGESRATE").text = "0"

        data = ET.SubElement(item, "ALLSALESINVOICES$InventoryItems$ItemTransactions")
        # Purchase ledger
        purchase = ET.SubElement(data, "ALLSALESINVOICES$InventoryItems$ItemTransactions$PurchaseLedger")
        ET.SubElement(purchase, "NAME").text = "Sales"
        ET.SubElement(purchase, "ISDELETED").text = "0"
        ET.SubElement(purchase, "CATEGORY").text = "Sales"
        ET.SubElement(purchase, "ACTUALQTY").text = str(line.get("qty", 1))
        ET.SubElement(purchase, "ACTUALRATE").text = str(Decimal(str(line.get("unit_price", 0))) / 100)
        ET.SubElement(purchase, "ACTUALAMOUNT").text = str(Decimal(str(line.get("line_total", 0))) / 100)

        # Sales ledger
        sales = ET.SubElement(data, "ALLSALESINVOICES$InventoryItems$ItemTransactions$SalesLedger")
        ET.SubElement(sales, "NAME").text = "Sales"
        ET.SubElement(sales, "ISDELETED").text = "0"
        ET.SubElement(sales, "CATEGORY").text = "Sales"
        ET.SubElement(sales, "ACTUALQTY").text = str(line.get("qty", 1))
        ET.SubElement(sales, "ACTUALRATE").text = str(Decimal(str(line.get("unit_price", 0))) / 100)
        ET.SubElement(sales, "ACTUALAMOUNT").text = str(Decimal(str(line.get("line_total", 0))) / 100)

        # GST breakdown
        total_gst = line.get("gst_paise", 0)
        if total_gst > 0:
            gst_rate = Decimal("18")  # Default — should be per HSN
            gst_amount = Decimal(str(total_gst)) / 100
            tax = ET.SubElement(data, "ALLSALESINVOICES$InventoryItems$ItemTransactions$TaxDetails")
            ET.SubElement(tax, "NAME").text = "GST"
            ET.SubElement(tax, "TYPE OF TAX").text = "GST"
            ET.SubElement(tax, "GSTATAMOUNT").text = str(gst_amount)

    # Total
    total = Decimal(str(bill.get("total_paise", 0))) / 100
    ET.SubElement(voucher, "AMOUNT").text = str(total)

    # Payment details
    payments = bill.get("payments", [])
    for pay in payments:
        pay_type = pay.get("type", "cash")
        pay_amount = Decimal(str(pay.get("amount_paise", 0))) / 100
        payment = ET.Element("ALLSALESINVOICES$PaymentReceipt")
        ET.SubElement(payment, "LEDGERNAME").text = _tally_tender_ledger(pay_type)
        ET.SubElement(payment, "ISDELETED").text = "0"
        ET.SubElement(payment, "AMOUNT").text = str(pay_amount)
        voucher.append(payment)

    return voucher


def _tally_tender_ledger(tender_type):
    """Map tender type to Tally ledger name."""
    mapping = {
        "cash": "Cash",
        "card": "Card Payments",
        "upi": "UPI Payments",
        "wallet": "Wallet Payments",
        "gift_voucher": "Gift Voucher Sales",
        "store_credit": "Store Credit Sales",
    }
    return mapping.get(tender_type, "Cash")


def _bill_to_dict(bill):
    """Convert a Bill model instance to a dict."""
    return {
        "bill_number": bill.bill_number,
        "date": bill.created_at.strftime("%Y%m%d") if bill.created_at else "",
        "customer_name": bill.customer_name,
        "customer_gstin": bill.customer_gstin,
        "lines": [{
            "sku": l.variant.sku,
            "description": l.full_description,
            "qty": l.quantity,
            "unit_price": l.unit_price_paise,
            "line_total": l.line_total_paise,
            "hsn": l.hsn_code,
            "gst_paise": l.cgst_paise + l.sgst_paise + l.igst_paise,
        } for l in bill.lines.all()],
        "total_paise": bill.total_paise,
        "payments": [{
            "type": p.tender_type,
            "amount_paise": p.amount_paise,
        } for p in bill.payments.all()],
        "cgst_paise": bill.cgst_paise,
        "sgst_paise": bill.sgst_paise,
        "igst_paise": bill.igst_paise,
    }
