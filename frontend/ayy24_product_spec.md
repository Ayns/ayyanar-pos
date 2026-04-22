# AYY-24 v0.1 Product Spec — Billing Core, Offline Sync, Apparel Wedge

> Approved by board: AYY-6. Parent: [AYY-11 PoS](/AYY/issues/AYY-11).
> Status: v0.1 prototype spec — internal use, no external commitments.

## 1. Vision

A single codebase that powers an apparel retail POS terminal at the store level and a headless API backend in the cloud. The store box runs Django + Postgres + Redis + Celery inside Docker Compose, compiled where required via Nuitka. The cloud runs a multi-tenant Django service on AWS Mumbai. Offline-first is non-negotiable — a store must survive a complete network outage for weeks and reconcile flawlessly when connectivity returns.

**Wedge**: Indian apparel brands (single-store, then multi-store). The product differentiator is the size-color matrix first — no competing product treats size+color as a native SKU primitive with built-in stock tracking per variant.

## 2. Scope — v0.1

v0.1 delivers the minimum set of features that a real apparel store could operate a business day with, including compliance:

| # | Feature | Description | Owner |
|---|---------|-------------|-------|
| 1 | Product catalogue (apparel) | Style → Color → Size tree. Variant-level SKU, MRP, season tag. Cloud-authoritative. | AYY-26 |
| 2 | Till billing | Add items, apply discount, split-tender (Cash/UPI/Card/Credit), print receipt, close bill. | AYY-26 |
| 3 | Stock ledger (event-sourced) | Every mutation → append-only `StockEvent`. `on_hand` derived, never stored. | AYY-25 |
| 4 | Offline sync | Outbox → cloud ship (store→cloud), change-feed pull (cloud→store). Lammonotonic ordering. | AYY-25 |
| 5 | E-invoice stub | Placeholder for IRP submission. Records invoice data locally, queues for submission. IRP client from AYY-14 spike. | AYY-28 |
| 6 | GST calculation | CGST/SGST (intra-state) and IGST (inter-state) computed per line. HSN codes carried forward. | AYY-28 |
| 7 | Tally daily voucher export | XML generation (AYY-15 spike). One voucher per business day per store. | AYY-28 |
| 8 | Docker Compose store box | Single-command deploy: Django + Postgres + Redis + Nginx. | AYY-27 |
| 9 | HO console (prototype) | Web UI (React) for catalogue management and daily sales view. Multi-tenancy stub. | AYY-30 |
| 10 | Cloud multi-tenancy | Per-tenant store assignment via RLS. Prototype tenant onboarding flow. | AYY-30 |

**Deliberately out of scope for v0.1** (Phase 1+):
- Payment SDK integration (Pine Labs / Mswipe / Paytm) — manual entry fallback only
- Migration adapters (Tally/Vyapar/Marg/Gofrugal/Excel) — v0.2
- Real e-invoice IRP integration — stub only; real integration via contractor
- Inventory reorder alerts, purchase orders, vendor management
- Loyalty / membership / wallet
- Employee management, shift tracking, target achievement
- Advanced analytics / BI dashboards

## 3. Domain Model

### 3.1 Apparel Product Hierarchy

```
Brand (cloud)
└── Style
    ├── Color
    │   ├── Size S → Variant {sku, mrp, stock}
    │   ├── Size M → Variant
    │   └── Size L → Variant
    ├── Color Blue
    │   ├── Size S → Variant
    │   └── Size M → Variant
    └── Color Green
        └── Size S → Variant
```

**Canonical entities:**

| Entity | Key fields | Owner |
|--------|------------|-------|
| `ProductStyle` | style_id, name, category, season_tag | Cloud |
| `ProductColor` | color_id, style_id, hex_code | Cloud |
| `SizeDef` | size_id, color_id, label (S/M/L/XL) | Cloud |
| `Variant` | variant_id (=SKU), size_id, mrp_paise, cost_price_paise, stock_on_hand | Cloud (authoritative), Store (local copy) |
| `StockEvent` | store_id, outbox_id, variant_id, kind, delta, payload | Store (authoritative) |

Size labels use standard Indian apparel sizing: XS, S, M, L, XL, XXL, 28–44 (waist), free.

### 3.2 Billing / Invoice

```
Invoice {
    invoice_no          -- store-local monotonically increasing
    store_id
    tenant_id
    customer_name?      -- optional (B2C default)
    customer_gstin?     -- optional (B2B when GSTIN provided)
    lines[] {
        variant_id, qty, unit_price_paise, mrp_paise,
        hsn_code, cgst_pct, sgst_pct, igst_pct
    }
    payments[] {
        method: CASH|UPI|CARD|CREDIT, amount_paise, txn_ref?
    }
    discount_paise
    total_paise
    status: OPEN|SUBMITTED|CANCELLED
}
```

**Payment splitting rules (v0.1):**
- A single invoice may use multiple payment methods (e.g., Cash + UPI + Card)
- Split must exactly match invoice total (no rounding slack)
- Manual fallback: if card terminal is down, the cashier enters amount → auto-generates a "manual card" payment record
- UPI: fixed amount entry, no scan validation in v0.1
- Credit (store ledger): only for B2B / registered customers; creates a receivable in the Tally export

### 3.3 Compliance Model

| Requirement | v0.1 status | Notes |
|-------------|-------------|-------|
| GST calculation (CGST/SGST + IGST) | In-scope | Per-line computation; auto-detect intra vs inter state from customer GSTIN state code |
| E-invoice (IRP) | Stub | Queue invoice locally; real submission via contractor in Phase 1 |
| E-way bill | Out of scope v0.1 | Phase 1 |
| GSTR-1 / GSTR-3B | Out of scope v0.1 | Phase 1 |
| Tally daily voucher | In-scope | One XML per store per day; AYY-15 spike validated |
| Data residency | Non-negotiable | All data in `ap-south-1`; no data leaves India |

## 4. Offline Sync Architecture

See AYY-13 (R1) spike for the proven event-sourced outbox pattern. The v0.1 product spec adopts the locked decisions from that spike:

- **Stock**: Store → Cloud (one-way). `StockEvent` is store-authoritative. Cloud builds a projection (`CloudStockProjection`) from events.
- **Catalogue**: Cloud → Store (one-way). `CatalogUpdate` entries on a monotonic `feed_cursor`; stores pull via change feed.
- **Billing**: Tied to stock — every invoice line that deducts stock emits a `SALE` event. Returns emit `RETURN` events.
- **Idempotency**: `(store_id, outbox_id)` is the global uniqueness key. Cloud-side ingest is idempotent — duplicate shipments are safe.
- **Conflict resolution**: `PAYLOAD_DIVERGENCE` anomalies go to `PendingReconciliation` UI. No silent overwrites.
- **Clock**: Wall-clock is observed; Lamport `outbox_id` is authoritative for ordering.

### 4.1 Sync Topology

```
Store Box (Docker Compose)
├── Django (store API + till)
├── Postgres (stock_events, invoices, catalog)
├── Redis + Celery (drainer worker)
└── Nginx (till HTTPS)
       │ HTTP (batched, TLS)
       ▼
Cloud (AWS Mumbai ap-south-1)
├── Django (multi-tenant API)
├── Aurora (Postgres-compatible)
└── S3 (archival — receipts, IRP responses)
```

Network profile: store may be online continuously or offline for days/weeks. Sync must handle 7-day offline with 5k-line/day throughput (spike proved 4.57s reconcile, budget 30s).

## 5. Hardware Abstraction Layer (HAL) — v0.1 Stub

v0.1 includes a minimal HAL with mock implementations. Real driver integration is Phase 1.

| Peripheral | HAL v0.1 | Phase 1 |
|------------|----------|---------|
| Thermal printer | Mock (stdout) | Epson ESC/POS + TVS + Everycom |
| Barcode scanner | USB keyboard wedge (direct) | Honeywell |
| Card terminal | Mock | Pine Labs / Mswipe / Paytm EDC |
| Cash drawer | Mock (triggered by CASH payment) | Via EDC relay |
| Customer display | None | Secondary screen via HAL |

## 6. Deployment — Store Box

### 6.1 Docker Compose (AYY-27)

```yaml
version: "3.9"
services:
  web:         # Django (gunicorn + uvicorn for Celery beat)
  db:         # Postgres 16
  redis:      # Redis 7 (Celery broker)
  celery:     # Celery worker (drainer + e-invoice queue)
  nginx:      # Reverse proxy + till HTTPS
```

One `docker-compose.yml` per store. Single-command deploy: `docker compose up -d`.

### 6.2 Nuitka Compilation

Critical modules (licensing, sync engine, e-invoice) compiled to C extensions via Nuitka. The remainder stays as Python source. Nuitka step is part of the store-box build pipeline (AYY-27).

## 7. HO Console (AYY-30) — Prototype Scope

A React SPA served from the cloud Django backend:

- **Catalogue editor**: CRUD on Style → Color → Size → Variant. Bulk upload CSV.
- **Daily sales dashboard**: Per-store revenue, top SKUs, stock alerts.
- **Pending reconciliation queue**: Surface `PendingReconciliation` records from all stores. Operator actions: approve, dispute, manual adjust.
- **Tenant admin**: Create/assign stores to tenants. Toggle e-invoice per store.
- Auth: prototype email/password only. Phase 1: SSO / SAML.

## 8. Migration Adapters (AYY-29) — v0.1 Scoping

v0.1 includes **CSV import** for the initial product catalogue (one CSV → Style/Color/Size/Variant seeding). This is the minimum viable wedge importer.

**Phase 1+ adapters** (prioritized): Tally XML import → Excel (.xlsx) → Vyapar → Marg → Gofrugal.

## 9. Pricing — v0.1 (locked by board, AYY-11)

| Tier | Price | Scope |
|------|-------|-------|
| Starter | ₹999 / store / month | Single till, basic billing, offline sync, Tally export |
| Growth | ₹1,999 / store / month | Multi-till, e-invoice, HO console analytics, payment SDK |

v0.1 implements the Starter tier feature set. Pricing gating is internal — no paywall logic in prototype.

## 10. Success Criteria

| # | Criterion | Target |
|---|-----------|--------|
| 1 | Till can complete a full sales day (stock → invoice → receipt → Tally XML) | Manual test, single-store |
| 2 | Offline sync survives 7-day cable-pull, reconciles on reconnect with zero data loss | Property test from AYY-13 |
| 3 | Tally XML imports cleanly on Prime + Prime Server (AYY-15 spike goldens) | 24 golden files green |
| 4 | IRP client handles ≥22 error codes with deterministic routing | AYY-14 spike tests green |
| 5 | Store box deploys in <5 minutes from bare Docker | `docker compose up -d` |
| 6 | HO console can create a style, add colors/sizes, and push to store via change feed | Manual smoke test |

## 11. Execution Dependencies

| Subtask | Depends On | Notes |
|---------|------------|-------|
| AYY-24 (this spec) | — | Blocks all others |
| AYY-25 (sync engine) | AYY-24 | Reuses AYY-13 spike code |
| AYY-26 (POS terminal) | AYY-24 | React-based; consumes store API |
| AYY-27 (Docker Compose) | — | Parallel with AYY-24 |
| AYY-28 (compliance) | AYY-24 | Reuses AYY-14 + AYY-15 spikes |
| AYY-29 (migration adapters) | AYY-24 | CSV import only in v0.1 |
| AYY-30 (HO console) | AYY-24 | React SPA + multi-tenancy stub |

## 12. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tally ERP 9 vendor-EOL | Compliance for legacy stores | Phase 1 ships Prime + Prime Server first-class; ERP 9 best-effort |
| GSTN sandbox onboarding blocked | Can't test real IRP integration | AYY-18 RFQ out to 7 vendors; sandbox unblocked by CEO escalation if needed |
| Nuitka compilation on ARM store boxes | Store boxes may be ARM (Raspberry Pi) | Nuitka cross-compile or fallback to PyInstaller for ARM |
| Hardware certification timeline | Payment SDK / printer drivers may take months | v0.1 uses HAL stubs; Phase 1 parallel certification |
| Multi-tenant RLS complexity | Security risk if tenant isolation leaks | Phase 1 external security audit locked in plan |

## 13. Open Questions for Phase 1 Planning

These are intentionally deferred but tracked for the Phase 1 handoff:

1. **Pricing model for add-ons**: Per-till surcharge, per-seat analytics, storage overage — PM to draft.
2. **E-way bill integration**: Threshold ₹50k, inter-state only. When does it land in the compliance stack?
3. **Purchase order workflow**: Stores receive stock from HO or from vendors. PO system is a separate domain.
4. **Employee management**: Till user auth, shift assignment, target tracking — sales tool for larger chains.
5. **Hardware HAL production drivers**: Budget for Windows VMs on real store boxes? ARM vs x86 decision?
