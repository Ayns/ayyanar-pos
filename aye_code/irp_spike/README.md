# AYY-14 Phase 0 / R2 spike — e-invoice IRP integration reliability

Throwaway Django spike validating the IRP (Invoice Registration Portal) client
design before production build and before the e-invoice contractor is scoped.

## What this spike proves

1. **Retry policy is right-sized.** Transient network / HTTP-5xx / IRP-throttle
   errors recover without operator involvement. Permanent business errors
   (`2150`, `2172`, `2194`, …) never get retried — they go straight to DLQ so
   operators see them in the manual-resubmit tool.
2. **Error taxonomy is exhaustive for v1.** ≥10 distinct IRP error codes are
   classified into `{TRANSIENT, BUSINESS, SECURITY, OUTAGE, SCHEMA}`. Each
   class has a deterministic client reaction.
3. **Latency shape is known.** Empirical p50 / p95 / p99 of a 7-day run against
   the sandbox tells us whether a synchronous till-side submit is viable or
   whether we must always queue (we ship queued in v1 regardless — this just
   tightens SLOs).
4. **DLQ + runbook are real.** An operator can pull any failed submission by
   IRN attempt id, inspect the request / response / stack, and resubmit from
   the HO console.

## Scope simplifications (spike vs production)

- The IRP target is injectable. Default is an in-process **simulator** that
  replays the publicly-documented GSTN error taxonomy at tunable probabilities;
  production will point at `einv-apisandbox.nic.in` and later
  `einvoice1.gst.gov.in`. The simulator is the authority for the hermetic tests
  in this repo. The 7-day empirical run against the real sandbox is operator-
  triggered, not CI-triggered.
- Signing / auth-token refresh is modelled as a pluggable `AuthProvider`. The
  spike uses a stub; production swaps in the actual GSTN auth flow. The retry
  state machine is the same either way.
- Celery is not used. The submit loop is a plain function invoked by the
  harness. Celery's contribution (retry decorator + worker isolation +
  visibility-timeout) is orthogonal to the state machine we are validating.
- Persistence is SQLite `:memory:`. Production is Postgres on the store box.
  The ORM model is identical.

## Files

- `conf/settings.py`  — minimal Django settings (SQLite, one app)
- `irp_client/models.py` — `InvoiceSubmission`, `IrpAttempt`, `DeadLetter`
- `irp_client/error_taxonomy.py` — canonical IRP error code table + client
  handling class per code
- `irp_client/client.py` — retry/backoff state machine; promotes to DLQ on
  terminal classes; records every attempt for latency stats
- `irp_client/simulator.py` — injectable IRP target that models the
  documented error taxonomy, latency, throttle, and outage behaviour
- `irp_client/generator.py` — GST-compliant synthetic invoice payload builder
- `irp_client/harness.py` — 5-tenant, 200-invoice/day submission scheduler
- `irp_client/stats.py` — p50/p95/p99 latency + error-class histogram
- `tests/test_error_taxonomy.py` — every documented code has a class + action
- `tests/test_retry_state_machine.py` — property tests over attempt→DLQ flow
- `tests/test_latency_budget.py` — simulator-driven p99 regression gate
- `tests/test_harness_smoke.py` — 5-tenant × 200/day run completes cleanly

## Run

```
DJANGO_SETTINGS_MODULE=conf.settings python3 -m pytest -q
```

## Success criteria (from AYY-14)

1. p99 latency baseline from a 7-day sandbox run (operator step; harness
   writes raw data + `stats.py` computes percentiles).
2. Error taxonomy ≥10 distinct IRP codes with client-side handling.
3. Retry / backoff / DLQ strategy documented with SLOs and an operator
   runbook stub.
