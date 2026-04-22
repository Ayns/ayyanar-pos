"""All 24 generated vouchers must balance: sum of ALLLEDGERENTRIES = 0.

This is the invariant Prime Server enforces with error 6212. If the
generator ever drifts, Prime Server imports fail silently for the retail
cases that don't have that check turned on and loudly for the ones that
do. The test captures both — we never ship an unbalanced voucher to ANY
version.
"""
from __future__ import annotations

from decimal import Decimal
from xml.etree import ElementTree as ET

import pytest

from tally_client.scenarios import ALL_SCENARIOS
from tally_client.version_matrix import all_versions
from tally_client.xml_generator import generate


@pytest.mark.parametrize("version", all_versions(), ids=lambda v: v.value)
@pytest.mark.parametrize("scenario", ALL_SCENARIOS, ids=lambda s: s.scenario_id)
def test_ledger_entries_balance(version, scenario):
    xml = generate(scenario, version)
    root = ET.fromstring(xml)
    total = Decimal("0.00")
    for le in root.findall(".//ALLLEDGERENTRIES.LIST"):
        amt = le.findtext("AMOUNT") or "0"
        total += Decimal(amt)
    # Allow ±0.01 paisa drift only (that's what Prime Server allows too)
    assert abs(total) <= Decimal("0.01"), (
        f"{version.value}/{scenario.scenario_id} unbalanced: net={total}"
    )
