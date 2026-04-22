"""
Taxonomy sanity.

AYY-14 success criterion: ≥10 distinct IRP codes classified with a client
action. We check shape, coverage across all five live classes, and that the
classifier never returns ``None`` for unknown codes (unknowns are forced to
``SCHEMA`` so operators always see them).
"""
from __future__ import annotations

from irp_client.error_taxonomy import (
    BUSINESS_CODES,
    DUPLICATE_CODES,
    ErrorClass,
    OUTAGE_CODES,
    SCHEMA_CODES,
    SECURITY_CODES,
    TAXONOMY,
    THROTTLE_CODES,
    TRANSIENT_CODES,
    classify,
)


def test_taxonomy_has_at_least_ten_codes():
    assert len(TAXONOMY) >= 10


def test_every_live_class_has_a_representative():
    # The six handling classes all must have at least one code so the state
    # machine has something to dispatch to.
    for group in (
        BUSINESS_CODES,
        SCHEMA_CODES,
        SECURITY_CODES,
        THROTTLE_CODES,
        TRANSIENT_CODES,
        OUTAGE_CODES,
        DUPLICATE_CODES,
    ):
        assert group, f"empty class group: {group}"


def test_unknown_code_falls_back_to_schema():
    assert classify("9999_NEVER_SEEN") == ErrorClass.SCHEMA


def test_every_entry_has_client_action_text():
    for code, entry in TAXONOMY.items():
        assert entry.client_action, f"no client action for {code}"
        assert entry.description, f"no description for {code}"
