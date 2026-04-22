# AYY-15 Phase 0 / R3 spike — Tally export correctness across versions

Throwaway Django spike validating that our daily-sales XML voucher payloads
import cleanly and round-trip losslessly across three Tally versions:
Tally ERP 9 (Release 6.x), Tally Prime (2.x/3.x), and Tally Prime Server (4.x).

## What this spike proves

1. **One canonical XML generator handles all three versions.** Version
   differences are confined to a single capability matrix
   (`tally_client/version_matrix.py`). Downstream code never branches on
   "if version == ERP_9" outside that table.
2. **All 8 required scenarios serialise to a balanced voucher** — sum of
   `ALLLEDGERENTRIES.LIST` amounts is `0.00` ± 1 paisa for every (version,
   scenario) combination. That is the invariant Prime Server enforces
   with error 6212.
3. **Schema-level round-trip is lossless.** What goes in via
   `IMPORTDATA` comes back out via the Day Book export path with identical
   voucher number, date, line count, narration (including markdown-reason
   prefix), and tender structure.
4. **Error taxonomy is actionable.** 18 Tally response codes are classified
   into 6 action classes (`RETRY`, `REPAIR`, `MANUAL`, `SECURITY`,
   `DUPLICATE`, `SCHEMA`). Unknown codes fall to `SCHEMA` so the client
   never auto-retries an unclassified error.
5. **Diff-as-test-failure is real.** 24 committed golden-file fixtures
   (3 versions × 8 scenarios). A generator change that drifts any voucher
   byte-for-byte fails CI; regeneration is an explicit
   `python -m tally_client.golden --regenerate` with a human-reviewed diff.

## What this spike does **not** prove (Phase 1 carry-over)

The hermetic suite runs entirely against an in-process simulator — no
Windows VM, no Tally license. The simulator faithfully replays the
documented schema, version-specific validations, and error grammar but
cannot verify behaviour that only emerges on real Tally:

- Empirical import latency under a realistic daily voucher load.
- Concurrent voucher numbering collisions under parallel imports.
- How Tally's Day Book re-serialisation (whitespace normalisation,
  attribute order) interacts with our structural round-trip assertion.
- Master-data creation side-effects (new stock item, new ledger) that
  Tally auto-provisions on first import.

Phase 1 plan: stand up one Windows VM per Tally version, replay the
hermetic fixtures through the real HTTP-XML endpoint on `localhost:9000`,
and pin the empirical behaviour into a second-tier test that can be
skipped in CI but must pass pre-release. See AYY-15 comment for the
version-matrix decisioning handoff to PM + Django sr #2.

## The 8 scenarios

| scenario | kind | lines | tenders | GST cases |
|----------|------|-------|---------|-----------|
| cash_sale | Sales | 1 | Cash | 5% CGST/SGST |
| upi_sale | Sales | 1 | UPI | 12% CGST/SGST |
| mixed_tender_sale | Sales | 2 | Cash + UPI + Card | 5% + 12% |
| return_sale | Credit Note | 1 | Cash refund | 5% CGST/SGST |
| exchange_sale | Sales | 1 | Store Credit + Cash | 5% CGST/SGST |
| gst_credit_note | Credit Note | 1 | Party (B2B GSTIN) | 12% CGST/SGST |
| multi_line_mixed_gst | Sales | 3 | Card | 5% + 12% + 18% |
| manual_markdown_sale | Sales | 1 | Cash | 5%, 25% manager discount |

## Version matrix (docs-sourced, empirical verification pending Phase 1)

| capability | ERP 9 | Prime | Prime Server |
|------------|-------|-------|--------------|
| emits legacy `<PARTYNAME>` | ✓ | ✗ | ✗ |
| `<TARGETCOMPANY>` required in header | ✗ | ✗ | ✓ |
| `<GSTREGISTRATIONTYPE>` required on party | ✗ | ✓ | ✓ |
| GSTIN format validated at import | ✗ | ✓ | ✓ |
| HSN required when GST-enabled | ✗ | ✓ | ✓ |
| Credit note `<ISINVOICE>Yes</ISINVOICE>` required for GSTR | ✗ | ✓ | ✓ |
| Strict tender-sum balance check | ✗ | ✗ | ✓ |
| UDF tags require `TYPE`/`ISLIST` attributes | ✗ | ✓ | ✓ |

Everything in this table comes from the published Tally XML integration
docs. Phase 1's empirical pass either confirms each row or pins the
correction.

## Scope simplifications (spike vs production)

- Tally target is injectable. Default is `tally_client.simulator.TallySimulator`
  which replays the documented schema grammar. Production points at
  `http://{store-box}:9000` (ERP 9 / Prime single-user) or a Prime Server
  host. The simulator stays the authority for hermetic schema tests; the
  VM-backed tier is operator-triggered.
- Master data (stock items, ledgers, voucher types) is assumed pre-seeded
  on the Tally side. Phase 1 will add a "master bootstrap" path that
  creates missing masters before retrying the voucher import (error
  codes 6201, 6211, 6213 route into this repair path).
- No signing / no auth refresh. Prime Server's 7001 is modelled in the
  error taxonomy but not exercised; the production client will own the
  auth flow and feed codes back into this taxonomy.
- Persistence is in-memory only. Production will record every import
  attempt in an `IrpAttempt`-shaped table (same shape as the AYY-14 R2
  spike, intentionally, so the operator DLQ UI is one screen).

## Files

- `conf/settings.py` — minimal Django settings (SQLite, one app)
- `tally_client/version_matrix.py` — canonical version capability table
- `tally_client/scenarios.py` — the 8 daily-sales scenarios as pure data
- `tally_client/xml_generator.py` — deterministic Tally XML generator
- `tally_client/simulator.py` — in-process Tally import simulator
- `tally_client/error_taxonomy.py` — Tally response code table + action class
- `tally_client/golden.py` — golden-file fixture store + CLI regenerator
- `golden/{version}/{scenario}.xml` — 24 committed fixtures
- `tests/test_golden_files.py` — byte-diff each generated voucher vs golden
- `tests/test_voucher_balance.py` — every voucher nets to ±0.01 INR
- `tests/test_simulator_import.py` — every voucher imports cleanly
- `tests/test_round_trip.py` — import → export structural equivalence
- `tests/test_version_matrix.py` — version-specific behavioural guards
- `tests/test_error_taxonomy.py` — error classification invariants

## Running

```bash
python3 -m pytest -q                                   # hermetic suite
python3 -m tally_client.golden --regenerate            # refresh goldens
```

## Success criteria mapping

| criterion | status |
|-----------|--------|
| Golden files green on all 3 Tally versions × 8 scenarios | ✓ (24 fixtures, diff-as-failure) |
| Documented version compatibility matrix with feature flags | ✓ (`version_matrix.py` + README table) |
| Per-version smoke-test harness reusable in Phase 1 CI | ✓ (simulator-backed pytest parametrisation) |
| ≥10 distinct Tally error codes classified | ✓ (18 codes, 6 action classes) |
| Empirical behaviour on real Tally VMs | **Carry-over to Phase 1** — no Windows VMs / licenses in spike scope |
