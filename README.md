# Ayyyanar Tech — POS for Indian Apparel Retail

Point-of-sale software for Indian apparel retail brands. Single-store to multi-store, with offline-first sync, GST compliance, and Tally integration.

## Layout

```
.
├── README.md          — this file
├── ENGINEERING.md     — how we work
├── PROJECT_DOCUMENTATION.md — full project catalog
│
├── backend/           — Django backend
│   ├── backend/       — Django project (settings, urls, wsgi)
│   ├── backend/billing/     — Till billing module
│   ├── backend/catalogue/   — Product catalogue (apparel)
│   ├── backend/customers/   — Customer management
│   ├── backend/inventory/   — Stock ledger
│   ├── backend/irp/         — E-invoice IRP client
│   ├── backend/licence/     — Licence server
│   ├── backend/sync/        — Offline sync endpoints
│   ├── backend/tally/       — Tally daily voucher export
│   ├── backend/till/        — Till views
│   ├── backend/hoc/         — Head-office console
│   ├── irp_client/        — IRP retry/DLQ state machine
│   ├── sync_core/         — Outbox drainer + cloud replayer
│   ├── tally_client/        — Tally XML generator
│   ├── importers/           — CSV catalogue importer
│   ├── manage.py            — Django CLI
│   ├── docker-compose.yml   — Store box deployment
│   ├── nginx/               — Reverse proxy config
│   └── build.sh / deploy.sh — Deployment scripts
│
├── frontend/          — React POS terminal + HO console
│   ├── src/             — POS terminal app (React)
│   ├── public/          — HTML, manifest, service worker
│   ├── pos-app/         — Alternative POS prototype
│   └── package.json     — Dependencies
│
└── spikes/            — Technical spikes & prototypes
    ├── pos_spike/       — Event-sourced outbox (AYY-13)
    ├── irp_spike/       — E-invoice IRP reliability (AYY-14)
    └── tally_spike/     — Tally export correctness (AYY-15)
```

## Getting Started

### Backend (Django)

```sh
cd backend
python manage.py migrate
python manage.py runserver
```

### Frontend (React)

```sh
cd frontend
npm install
npm start
```

### Docker Compose (full stack)

```sh
cd backend
docker-compose up -d
```

## Stack

- **Backend:** Python 3.12 + Django + Postgres 16 + Redis 7 + Celery
- **Frontend:** React + IndexedDB (offline) + Service Worker
- **Infra:** Docker Compose, Nginx, Nuitka for critical modules
- **Tests:** pytest (backend), Jest/React Testing Library (frontend)
