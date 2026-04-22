"""Tally error taxonomy unit tests.

Unknown codes fall to SCHEMA so operators never see an auto-retry on a
code we haven't classified. Terminal business codes never retry. Transient
codes are retry-safe.
"""
from __future__ import annotations

from tally_client.error_taxonomy import (
    ERRORS,
    TallyAction,
    classify,
    codes_for_version,
)


def test_unknown_code_falls_to_schema():
    err = classify("9999")
    assert err.action == TallyAction.SCHEMA
    assert err.code == "9999"


def test_ok_code_is_retry_class():
    err = classify("0")
    # "0" is not actually an error; it slots into RETRY to keep the action
    # enum total for the happy path. The client checks `ok` on the result,
    # not the action class, so this is cosmetic.
    assert err.action == TallyAction.RETRY


def test_duplicate_code_is_idempotent():
    err = classify("6210")
    assert err.action == TallyAction.DUPLICATE


def test_authentication_code_is_security():
    err = classify("7001")
    assert err.action == TallyAction.SECURITY


def test_hsn_missing_is_schema_not_business():
    # HSN missing is OUR bug (payload malformed), not an operator fix
    err = classify("6403")
    assert err.action == TallyAction.SCHEMA


def test_ledger_missing_is_repair():
    err = classify("6201")
    assert err.action == TallyAction.REPAIR


def test_covers_at_least_ten_codes():
    # Board success criterion: ≥10 distinct codes catalogued
    distinct_biz = [c for c, e in ERRORS.items() if e.action != TallyAction.RETRY]
    assert len(distinct_biz) >= 10, f"only {len(distinct_biz)} classified"


def test_target_company_code_is_prime_server_only():
    code = "7102"
    erp9_codes = codes_for_version("erp9")
    prime_codes = codes_for_version("prime")
    ps_codes = codes_for_version("prime_server")
    assert code in ps_codes
    assert code not in erp9_codes
    assert code not in prime_codes
