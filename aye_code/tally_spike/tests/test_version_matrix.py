"""Version-matrix behavioural differences the generator + simulator must honour."""
from __future__ import annotations

import pytest

from tally_client.scenarios import cash_sale
from tally_client.simulator import TallySimulator
from tally_client.version_matrix import TallyVersion, capabilities
from tally_client.xml_generator import generate


def test_erp9_emits_legacy_partyname():
    xml = generate(cash_sale(), TallyVersion.ERP_9)
    assert "<PARTYNAME>" in xml
    assert "<PARTYLEDGERNAME>" in xml


def test_prime_omits_legacy_partyname():
    xml = generate(cash_sale(), TallyVersion.PRIME)
    assert "<PARTYNAME>" not in xml
    assert "<PARTYLEDGERNAME>" in xml


def test_prime_server_requires_target_company_in_header():
    xml = generate(cash_sale(), TallyVersion.PRIME_SERVER)
    assert "<TARGETCOMPANY>" in xml


def test_erp9_skips_target_company():
    xml = generate(cash_sale(), TallyVersion.ERP_9)
    assert "<TARGETCOMPANY>" not in xml


def test_prime_rejects_malformed_gstin():
    from tally_client.scenarios import gst_credit_note
    # Corrupt the GSTIN via a new scenario object
    scenario = gst_credit_note()
    broken = scenario.__class__(**{**scenario.__dict__, "party_gstin": "NOT-A-VALID-GSTIN"})
    xml = generate(broken, TallyVersion.PRIME)
    sim = TallySimulator(TallyVersion.PRIME)
    result = sim.post(xml)
    assert result.code == "6401", result.message


def test_erp9_tolerates_malformed_gstin():
    # ERP 9 does NOT validate GSTIN at import time (documented quirk)
    from tally_client.scenarios import gst_credit_note
    scenario = gst_credit_note()
    broken = scenario.__class__(**{**scenario.__dict__, "party_gstin": "INVALID"})
    xml = generate(broken, TallyVersion.ERP_9)
    sim = TallySimulator(TallyVersion.ERP_9)
    result = sim.post(xml)
    assert result.ok


def test_prime_server_rejects_unbalanced_voucher():
    # Take a valid voucher then knock the cash tender leg out of balance
    from tally_client.scenarios import cash_sale
    xml = generate(cash_sale(), TallyVersion.PRIME_SERVER)
    # Target the Cash ledger specifically (second 1499.00 — the tender leg;
    # the first is the inventory AMOUNT which isn't summed for the check).
    cash_marker = "<LEDGERNAME>Cash</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>1499.00</AMOUNT>"
    broken = cash_marker.replace("1499.00", "1399.00")
    broken_xml = xml.replace(cash_marker, broken, 1)
    assert broken_xml != xml, "failed to poison Cash ledger amount"
    sim = TallySimulator(TallyVersion.PRIME_SERVER)
    result = sim.post(broken_xml)
    assert result.code == "6212", result.message


def test_capabilities_match_expected_keys():
    # Regression guard: the three versions must all expose the same surface
    erp = capabilities(TallyVersion.ERP_9)
    prime = capabilities(TallyVersion.PRIME)
    ps = capabilities(TallyVersion.PRIME_SERVER)
    # Sanity: Prime Server is the only version that enforces tender sum strictly
    assert not erp.strict_tender_sum_check
    assert not prime.strict_tender_sum_check
    assert ps.strict_tender_sum_check
    # Target-company requirement is Prime Server only
    assert not erp.requires_target_company
    assert not prime.requires_target_company
    assert ps.requires_target_company
