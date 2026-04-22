"""Golden-file fixture store for (version, scenario) voucher payloads.

Files live at `golden/{version}/{scenario_id}.xml`. The test suite diffs the
current generator output against these; any divergence is a failure. Files
are regenerated with `python -m tally_client.golden --regenerate`.

This module also exposes `assert_matches_golden` so tests can use it
directly without duplicating load logic.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from xml.etree import ElementTree as ET

from .scenarios import ALL_SCENARIOS, Scenario
from .version_matrix import TallyVersion, all_versions
from .xml_generator import generate


GOLDEN_ROOT = Path(__file__).resolve().parent.parent / "golden"


def path_for(version: TallyVersion, scenario_id: str) -> Path:
    return GOLDEN_ROOT / version.value / f"{scenario_id}.xml"


def load(version: TallyVersion, scenario_id: str) -> str:
    p = path_for(version, scenario_id)
    if not p.exists():
        raise FileNotFoundError(
            f"No golden file for ({version.value}, {scenario_id}) at {p}. "
            "Run `python -m tally_client.golden --regenerate`."
        )
    return p.read_text(encoding="utf-8")


def write(version: TallyVersion, scenario_id: str, xml: str) -> None:
    p = path_for(version, scenario_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(xml, encoding="utf-8")


def regenerate_all() -> list[tuple[TallyVersion, str, Path]]:
    written: list[tuple[TallyVersion, str, Path]] = []
    for version in all_versions():
        for scenario in ALL_SCENARIOS:
            xml = generate(scenario, version)
            write(version, scenario.scenario_id, xml)
            written.append((version, scenario.scenario_id,
                            path_for(version, scenario.scenario_id)))
    return written


def assert_matches_golden(version: TallyVersion, scenario: Scenario) -> None:
    expected = load(version, scenario.scenario_id)
    actual = generate(scenario, version)
    if expected != actual:
        # Normalise trailing whitespace differences but keep structural drift
        if expected.rstrip() == actual.rstrip():
            return
        raise AssertionError(
            f"Golden drift for ({version.value}, {scenario.scenario_id}). "
            f"Regenerate with `python -m tally_client.golden --regenerate` "
            f"after confirming the change is intentional.\n"
            f"--- expected ---\n{expected[:2000]}\n"
            f"--- actual   ---\n{actual[:2000]}"
        )


def _cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--regenerate", action="store_true")
    args = parser.parse_args()
    if args.regenerate:
        written = regenerate_all()
        for v, s, p in written:
            print(f"wrote {p}")
        print(f"total: {len(written)} fixtures")
        return
    parser.print_help()


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "conf.settings")
    import django
    django.setup()
    _cli()
