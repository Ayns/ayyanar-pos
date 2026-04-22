"""Re-export Tally spike code for backwards compatibility. Canonical code now
in storebox.tally_client."""
from tally_client.xml_generator import generate, to_xml_str, to_xml_bytes
from tally_client.version_matrix import TallyVersion, capabilities
from tally_client.scenarios import (
    Scenario, LineItem, Tender, TenderKind, VoucherKind,
    cash_sale, upi_sale, mixed_tender_sale, return_sale,
    exchange_sale, gst_credit_note, multi_line_mixed_gst,
    manual_markdown_sale, ALL_SCENARIOS, scenarios_by_id,
)
from tally_client.error_taxonomy import classify, TallyError, TallyAction
