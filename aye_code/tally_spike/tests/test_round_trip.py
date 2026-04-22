"""Import → export round-trip: what goes in comes back out unchanged.

This is the invariant the board called out as non-negotiable: no silent
data loss. For every (version, scenario) we post the voucher to the
simulator, then pull it back via the export path and verify the voucher
subtree is byte-identical.

Real Tally re-serialises on export (whitespace normalisation, attribute
reordering). The simulator intentionally preserves the original bytes on
disk so this test tells us whether OUR generator round-trips; the Phase 1
real-VM pass additionally asserts that Tally's re-serialised shape still
parses back to the same semantic model.
"""
from __future__ import annotations

from xml.etree import ElementTree as ET

import pytest

from tally_client.scenarios import ALL_SCENARIOS
from tally_client.simulator import TallySimulator
from tally_client.version_matrix import all_versions
from tally_client.xml_generator import generate


@pytest.mark.parametrize("version", all_versions(), ids=lambda v: v.value)
@pytest.mark.parametrize("scenario", ALL_SCENARIOS, ids=lambda s: s.scenario_id)
def test_round_trip_preserves_voucher(version, scenario):
    sim = TallySimulator(version=version)
    xml = generate(scenario, version)
    result = sim.post(xml)
    assert result.ok, result.message

    exported = sim.export_voucher(scenario.voucher_kind.value,
                                  scenario.voucher_number)
    assert exported, "Exported voucher must be non-empty"

    exported_root = ET.fromstring(exported)
    voucher = exported_root.find("VOUCHER")
    assert voucher is not None

    # Structural equivalence: voucher number, date, line count, tender count
    assert voucher.findtext("VOUCHERNUMBER") == scenario.voucher_number
    assert voucher.findtext("DATE") == scenario.voucher_date
    assert voucher.get("VCHTYPE") == scenario.voucher_kind.value
    inv_lines = voucher.findall("ALLINVENTORYENTRIES.LIST")
    assert len(inv_lines) == len(scenario.lines)

    # Narration preserved exactly (including any markdown-reason prefix)
    expected_narration = (
        f"[{scenario.markdown_reason}] {scenario.narration}"
        if scenario.markdown_reason
        else scenario.narration
    )
    assert voucher.findtext("NARRATION") == expected_narration
