# AYY-13 Phase 0 / R1 spike — event-sourced outbox prototype

Throwaway prototype validating the sync-conflict model before Phase 1.

## Scope simplifications (spike vs production)

- Physical DB separation (per-store Postgres ↔ cloud Aurora) is simulated
  inside one SQLite file using the `side` column on every table. Production
  will have two Django projects on two databases speaking HTTP. The
  algorithm being proven (append-only event log + idempotent replay +
  cloud-side `on_hand` reconstruction) is unchanged by that move.
- Celery is not used. The drainer is a plain function invoked by the
  harness. Celery's contribution (retry + backoff + worker isolation) is
  orthogonal to invariant correctness.
- HTTP transport is simulated in-process with an injectable `DrainSink`
  that can be toggled offline to "pull the cable".
- Clock skew is simulated by giving each store an independently-offsetable
  monotonic clock. Lamport-style `(store_id, outbox_id)` is the actual
  ordering primitive; wall-clock timestamps are observed but not trusted
  for conflict resolution.

## Files

- `conf/settings.py`  — minimal Django settings (SQLite, one app)
- `sync_core/models.py` — `Product`, `StockEvent`, `SyncOutbox`,
  `CloudEvent`, `CloudStockProjection`, `CatalogUpdate`, `ChangeFeedCursor`
- `sync_core/store.py` — store-side APIs (`record_sale`, `record_receive`,
  `record_markdown`, `record_adjustment`)
- `sync_core/drainer.py` — outbox → cloud shipper (idempotent on
  `(store_id, outbox_id)`)
- `sync_core/replayer.py` — cloud → store catalogue change-feed pull
- `sync_core/cloud.py` — cloud ingest + projection rebuild
- `tests/test_invariant.py` — property-based: `sum(events) == on_hand`
  for any interleaving under adversarial partition schedules
- `tests/test_drill.py` — 3 concurrent tills, randomized offline windows
  up to 7 days, specific conflict scenarios from the spike brief
- `tests/test_reconcile_benchmark.py` — 7-day offline × 5k-line/day
  reconcile budget (target <30s)

## Run

```
DJANGO_SETTINGS_MODULE=conf.settings python3 -m pytest -q
```

## Success criteria (from AYY-13)

1. Property test passes 10k generated histories: invariant holds.
2. Reconcile time after 7-day offline: <30s on a 5k-line/day profile.
3. No silent data loss; all anomalies surface in pending-reconciliation.
