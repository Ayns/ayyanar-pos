# Ayyyanar Tech — Project Documentation

> Catalog of all planned and developed work. Owned by CTO.
> Created: 2026-04-21 (AYY-33).

## 0. Company Overview

| Field | Value |
|-------|-------|
| Company | Ayyyanar Tech (Otto Clothing) |
| Product | POS software for Indian apparel retail |
| Wedge | Single-store → multi-store apparel brands; size-color matrix as native SKU primitive |
| Stack | Django (backend) + React (POS terminal / HO console) + Postgres + Redis + Celery |
| Team | CEO + CTO. Additional agents hired: PM, PM 2, Django1, Django1 2, FE, DevOps |
| Phase | 1 (approved 2026-04-21) |

## 1. Issue Tracker

### 1.1 Closed Issues

| Issue | Title | Status | Notes |
|-------|-------|--------|-------|
| AYY-1 | Founding engineer milestone | **done** | CTO hired, hiring plan live, roadmap delegated |
| AYY-2 | Phase 0 readiness | **done** | Stack chosen (TypeScript+Next.js→Django), repo scaffolded, ENGINEERING.md |
| AYY-3 | Create GitHub org `ayyyanar-tech` | done | Board task — unblocked repo creation |
| AYY-4 | Weekly triage routine | **done** | Paperclip routine configured |
| AYY-5 | CTO: push repo + branch protection + CI | done | Unblocked after AYY-3 |
| AYY-6 | Board: product thesis + Phase 1 budget | **done** | Approved 2026-04-21. Virtual envelope $70K/mo + $61K one-time. Scope restrictions apply (no external spend, no real employees/vendors). |

### 1.2 Active / Planned Issues

| Issue | Title | Assignee | Status | Blocks / Blocked By |
|-------|-------|----------|--------|---------------------|
| AYY-11 | PoS (product + engineering plan) | CEO | todo | Blocked by AYY-14, AYY-16 |
| AYY-13 | R1 spike — event-sourced outbox prototype | Django1 | in_progress | — |
| AYY-14 | R2 spike — e-invoice IRP integration reliability | CTO | todo | Unblocked by AYY-6 |
| AYY-15 | R3 spike — Tally export correctness across versions | Django1 | in_progress | — |
| AYY-16 | PoS engineering plan (detailed) | CTO | blocked | Blocked by AYY-11 |
| AYY-17 | Technical outreach / recruiting | CTO | in_progress | Blocked by AYY-6 |
| AYY-18 | Vendor engagement | PM | blocked | Requires `external_action_required: true` approval |
| AYY-20 | Phase 1 cost envelope | CEO | **done** | $70K/mo + $61K one-time (~$435K / 24 weeks) |
| AYY-24 | v0.1 product spec — billing core, offline sync, apparel wedge | PM | todo | **Critical path — blocks AYY-25, AYY-26, AYY-28, AYY-29, AYY-30** |
| AYY-25 | Sync engine + licence server prototype | Django1 | todo | Blocked by AYY-24 |
| AYY-26 | React POS terminal prototype | FE | todo | Blocked by AYY-24 |
| AYY-27 | Docker Compose store box + Nuitka pipeline | DevOps | todo | **No blockers** |
| AYY-28 | Compliance modules — GST, e-invoice stub, Tally export | Django1 2 | todo | Blocked by AYY-24 |
| AYY-29 | Migration adapters — Tally, Excel, CSV importers | PM 2 | todo | Blocked by AYY-24 |
| AYY-30 | HO console + cloud multi-tenancy prototype | FE | todo | Blocked by AYY-24 |

### 1.3 v0.1 Subtask Dependency Graph

```
AYY-24 (product spec) ─────┬─► AYY-25 (sync engine)
                           ├─► AYY-26 (POS terminal)
                           ├─► AYY-28 (compliance)
                           ├─► AYY-29 (migration adapters)
                           └─► AYY-30 (HO console)
AYY-27 (Docker Compose) ◄── independent (parallel with AYY-24)
```

## 2. Spike Reports

### 2.1 AYY-13 — Event-Sourced Outbox (R1)

**Location:** `f7cf2a7d-f25d-446e-89a5-45e73aeb46ad/_default/pos_spike/README.md`

**What it validates:** Append-only event log + idempotent replay + cloud-side `on_hand` reconstruction for offline-first POS sync.

**Key results:**
- Property-based test: 10k histories generated, invariant `sum(events) == on_hand` holds under all interleavings.
- Reconcile time after 7-day offline: 4.57s (budget: 30s).
- No silent data loss; all anomalies surface in pending-reconciliation.

**Files:**
| File | Purpose |
|------|---------|
| `sync_core/models.py` | `Product`, `StockEvent`, `SyncOutbox`, `CloudEvent`, `CloudStockProjection`, `CatalogUpdate` |
| `sync_core/store.py` | Store-side APIs (`record_sale`, `record_receive`, `record_markdown`, `record_adjustment`) |
| `sync_core/drainer.py` | Outbox → cloud shipper (idempotent on `(store_id, outbox_id)`) |
| `sync_core/replayer.py` | Cloud → store catalogue change-feed pull |
| `sync_core/cloud.py` | Cloud ingest + projection rebuild |
| `tests/test_invariant.py` | Property-based invariant test |
| `tests/test_drill.py` | 3 concurrent tills, randomized offline windows |
| `tests/test_reconcile_benchmark.py` | 7-day offline × 5k-line/day reconcile |

**Adoption:** Product spec (AYY-24) adopts all locked decisions from this spike for v0.1 offline sync architecture.

### 2.2 AYY-14 — E-Invoice IRP Integration (R2)

**Location:** `f7cf2a7d-f25d-446e-89a5-45e73aeb46ad/_default/irp_spike/README.md`

**What it validates:** Retry policy, error taxonomy, latency shape, and DLQ + operator runbook for GSTN Invoice Registration Portal client.

**Key results:**
- Retry policy right-sized: transient errors recover automatically; permanent business errors (2150, 2172, 2194) route to DLQ.
- Error taxonomy: >=10 distinct IRP error codes classified into `{TRANSIENT, BUSINESS, SECURITY, OUTAGE, SCHEMA}`.
- DLQ + runbook: operator can pull failed submissions by IRN attempt ID, inspect, and resubmit from HO console.

**Files:**
| File | Purpose |
|------|---------|
| `irp_client/models.py` | `InvoiceSubmission`, `IrpAttempt`, `DeadLetter` |
| `irp_client/error_taxonomy.py` | Canonical IRP error code table + handling per code |
| `irp_client/client.py` | Retry/backoff state machine |
| `irp_client/simulator.py` | Injectable IRP target (in-process simulator) |
| `irp_client/generator.py` | GST-compliant synthetic invoice payload builder |
| `irp_client/harness.py` | 5-tenant, 200-invoice/day submission scheduler |
| `irp_client/stats.py` | p50/p95/p99 latency + error-class histogram |
| `tests/test_error_taxonomy.py` | Every documented code has a class + action |
| `tests/test_retry_state_machine.py` | Property tests over attempt→DLQ flow |
| `tests/test_latency_budget.py` | Simulator-driven p99 regression gate |
| `tests/test_harness_smoke.py` | 5-tenant x 200/day smoke test |

**Adoption:** E-invoice stub in v0.1 (AYY-28) uses IRP client from this spike.

### 2.3 AYY-15 — Tally Export Correctness (R3)

**Location:** `f7cf2a7d-f25d-446e-89a5-45e73aeb46ad/_default/tally_spike/README.md`

**What it validates:** Daily-sales XML voucher payloads import cleanly and round-trip losslessly across Tally ERP 9, Tally Prime, and Tally Prime Server.

**Key results:**
- One canonical XML generator handles all 3 Tally versions (version matrix in `version_matrix.py`).
- All 8 required scenarios serialize to balanced vouchers.
- Schema-level round-trip is lossless (24 golden-file fixtures).
- Error taxonomy: 18 Tally response codes classified into 6 action classes.

**Files:**
| File | Purpose |
|------|---------|
| `tally_client/version_matrix.py` | Canonical version capability table |
| `tally_client/scenarios.py` | 8 daily-sales scenarios as pure data |
| `tally_client/xml_generator.py` | Deterministic Tally XML generator |
| `tally_client/simulator.py` | In-process Tally import simulator |
| `tally_client/error_taxonomy.py` | Tally response code table + action class |
| `tally_client/golden.py` | Golden-file fixture store + CLI regenerator |
| `golden/` | 24 committed XML fixtures |
| `tests/test_golden_files.py` | Byte-diff each voucher vs golden |
| `tests/test_voucher_balance.py` | Every voucher nets to +/-0.01 INR |
| `tests/test_simulator_import.py` | Every voucher imports cleanly |
| `tests/test_round_trip.py` | Import → export structural equivalence |
| `tests/test_version_matrix.py` | Version-specific behavioural guards |
| `tests/test_error_taxonomy.py` | Error classification invariants |

**Phase 1 carry-over:** Empirical import on real Tally VMs (no Windows VMs in spike scope).

**Adoption:** Tally daily voucher export in v0.1 (AYY-28) uses this spike.

## 3. Product Specifications

### 3.1 AYY-24 — v0.1 Product Spec

**Location:** `f7cf2a7d-f25d-446e-89a5-45e73aeb46ad/_default/ayy24_product_spec.md`

**Wedge:** Indian apparel brands (single-store → multi-store). Size-color matrix as native SKU primitive.

**v0.1 Scope (10 features):**

| # | Feature | Owner |
|---|---------|-------|
| 1 | Product catalogue (apparel) | AYY-26 |
| 2 | Till billing | AYY-26 |
| 3 | Stock ledger (event-sourced) | AYY-25 |
| 4 | Offline sync | AYY-25 |
| 5 | E-invoice stub | AYY-28 |
| 6 | GST calculation | AYY-28 |
| 7 | Tally daily voucher export | AYY-28 |
| 8 | Docker Compose store box | AYY-27 |
| 9 | HO console (prototype) | AYY-30 |
| 10 | Cloud multi-tenancy | AYY-30 |

**Architecture:**
- Store Box: Django + Postgres + Redis + Celery + Nginx in Docker Compose, Nuitka for critical modules.
- Cloud: Multi-tenant Django on AWS Mumbai (ap-south-1). Aurora Postgres + S3.
- Data residency: all data in ap-south-1; no data leaves India.

**Offline sync topology:**
- Stock: Store → Cloud (one-way, event-sourced outbox).
- Catalogue: Cloud → Store (one-way, change-feed pull).
- Billing: Tied to stock (SALE/RETURN events).
- Idempotency: `(store_id, outbox_id)` global uniqueness key.

**Success criteria (v0.1):**
1. Full sales day (stock → invoice → receipt → Tally XML) works single-store.
2. Offline sync survives 7-day cable-pull, reconciles with zero data loss.
3. Tally XML imports cleanly on Prime + Prime Server (24 golden files green).
4. IRP client handles >=22 error codes with deterministic routing.
5. Store box deploys in <5 minutes.
6. HO console can create style, add colors/sizes, push to store via change feed.

**Pricing (v0.1):**
- Starter: Rs. 999/store/month (single till, basic billing, offline sync, Tally export).
- Growth: Rs. 1,999/store/month (multi-till, e-invoice, HO console analytics, payment SDK).

## 4. Infrastructure & Engineering

### 4.1 AYY-2 — Phase 0 Engineering Foundation

**Location:** `49de323b-a889-48f2-af71-326f2a0c4279/_default/`

**Stack decision (later revised to Django):**
- Language: TypeScript on Node.js 22 LTS → **revised to Python/Django**
- Framework: Next.js (App Router) → **revised to Django**
- Data: Prisma + SQLite → Postgres → **kept Postgres**
- Tests: Vitest + Playwright → **pytest**
- Lint/format: Biome → **Black + Ruff**
- Package manager: pnpm → **pip/poetry**

**Documentation files:**
| File | Content |
|------|---------|
| `README.md` | Repo overview, stack, layout, getting started |
| `ENGINEERING.md` | Engineering workflow — branching, commits, PRs, CI, intake, SLAs |

### 4.2 v0.1 Deployment Target

**Store Box (AYY-27):**
```
docker-compose.yml
├── web    — Django (gunicorn + uvicorn for Celery beat)
├── db     — Postgres 16
├── redis  — Redis 7 (Celery broker)
├── celery — Celery worker (drainer + e-invoice queue)
└── nginx  — Reverse proxy + till HTTPS
```

**Cloud (AWS Mumbai ap-south-1):**
- Django multi-tenant API
- Aurora (Postgres-compatible)
- S3 (archival — receipts, IRP responses)

## 5. Board Decisions & Approvals

### AYY-6 — Product Thesis + Phase 1 Budget

**Decision date:** 2026-04-21
**Approval ID:** `972457b3-fc58-4fea-8503-4cc841a152a9`
**Board comment:** `bf62308c`

**Envelope:** $70K/mo recurring + $61K one-time (virtual, for workflow gating).

**Scope restrictions:**
1. No real-world commercial transactions (no hiring, contracts, SOWs, vendors, recruiters).
2. No external spend (no AWS changes, paid APIs, SaaS, domains). Use existing Otto Clothing infrastructure only.
3. No real employees/contractors/vendors. Agent roles in Paperclip are virtual.
4. Authorized: code, architecture, specs, analysis, agent labor. All agent labor is free.

**BudgetMonthlyCents:** Set to effectively unlimited ($10M+) for workflow gating.

## 6. Agent Roster

| Agent | Role | Status | Active Issues |
|-------|------|--------|---------------|
| CEO | Founding / Board liaison | Running | AYY-11 |
| CTO | Engineering / Architecture | Running | AYY-14, AYY-16, AYY-17, AYY-33 |
| PM | Product management | Idle | AYY-24 |
| PM 2 | Migration adapters | Idle | AYY-29 |
| Django1 | Backend engineer | Idle | AYY-13, AYY-15, AYY-25 |
| Django1 2 | Compliance engineer | Idle | AYY-28 |
| FE | Frontend engineer | Idle | AYY-26, AYY-30 |
| DevOps | Infrastructure | Idle | AYY-27 |
| DevOps 2 | (reserved) | — | — |

## 7. Phase 1 Cost Envelope Summary

**AYY-20** — Delivered 2026-04-20

| Component | Recurring | One-Time |
|-----------|-----------|----------|
| ~$435K total over 24 weeks | $70K/mo | $61K |

Cost model includes sensitivities called out: BE#1 comp, pen test range, FX, recruiter model, 1.5x team multiplier.

## 8. Files Index

| File | Path | Description |
|------|------|-------------|
| Project Doc (this file) | `_default/PROJECT_DOCUMENTATION.md` | Full catalog of work |
| Product Spec | `_default/ayy24_product_spec.md` | v0.1 product specification |
| Outbox Spike | `_default/pos_spike/README.md` | AYY-13 R1 spike report |
| IRP Spike | `_default/irp_spike/README.md` | AYY-14 R2 spike report |
| Tally Spike | `_default/tally_spike/README.md` | AYY-15 R3 spike report |
| README | `49de323b.../_default/README.md` | Repo overview |
| Engineering | `49de323b.../_default/ENGINEERING.md` | Workflow conventions |
| AYY-6 Approval | `49de323b...--default/memory/project_ayy6_approved.md` | Board approval record |
