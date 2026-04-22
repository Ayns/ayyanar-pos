"""Diff the XML generator output against the committed golden fixtures.

Every (version, scenario) pair must match byte-for-byte. Deliberate schema
changes require running `python -m tally_client.golden --regenerate` and
reviewing the diff.
"""
from __future__ import annotations

import pytest

from tally_client.golden import assert_matches_golden
from tally_client.scenarios import ALL_SCENARIOS
from tally_client.version_matrix import all_versions


@pytest.mark.parametrize("version", all_versions(), ids=lambda v: v.value)
@pytest.mark.parametrize("scenario", ALL_SCENARIOS, ids=lambda s: s.scenario_id)
def test_matches_golden(version, scenario):
    assert_matches_golden(version, scenario)
