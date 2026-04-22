"""Simulator-driven import tests across (version × scenario).

Each generated voucher must import cleanly into the corresponding version's
simulator. The simulator models the validations each version actually runs
(TARGETCOMPANY for Prime Server, GSTIN format for Prime, HSN requirement,
GSTREGISTRATIONTYPE requirement, tender-sum balance). A success means the
payload wouldn't be rejected for any schema-level reason on that version.
"""
from __future__ import annotations

import pytest

from tally_client.scenarios import ALL_SCENARIOS
from tally_client.simulator import TallySimulator
from tally_client.version_matrix import all_versions
from tally_client.xml_generator import generate


@pytest.mark.parametrize("version", all_versions(), ids=lambda v: v.value)
@pytest.mark.parametrize("scenario", ALL_SCENARIOS, ids=lambda s: s.scenario_id)
def test_import_accepted(version, scenario):
    sim = TallySimulator(version=version)
    xml = generate(scenario, version)
    result = sim.post(xml)
    assert result.ok, (
        f"{version.value}/{scenario.scenario_id} rejected: "
        f"{result.code} {result.message}"
    )
    assert result.created == 1
    assert result.ignored == 0


@pytest.mark.parametrize("version", all_versions(), ids=lambda v: v.value)
def test_duplicate_detection(version):
    sim = TallySimulator(version=version)
    scenario = ALL_SCENARIOS[0]  # cash_sale
    xml = generate(scenario, version)
    first = sim.post(xml)
    assert first.ok, first.message
    second = sim.post(xml)
    assert not second.ok
    assert second.code == "6210"
    assert second.error.action.value == "duplicate"
