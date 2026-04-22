# Ayyyanar Tech

Single-node engineering workspace for Ayyyanar Tech v0.1. No product thesis yet — this repo holds the engineering foundation so we can ship the second a thesis lands.

## Status

- **Phase:** 0 (engineering readiness). See issue `AYY-2`.
- **Team:** 1 (CTO). Second engineer only after v0.1 ships.
- **Budget:** $0 until the board sets a Phase 1 envelope.
- **Thesis:** TBD (tracked separately under `AYY-1`).

## Stack

Full rationale lives in the Phase 0 plan document on `AYY-2`. Short version:

- **Language:** TypeScript on Node.js 22 LTS
- **Framework:** Next.js (App Router) — web + API in one deploy unit
- **Data:** Prisma + SQLite locally, Postgres in prod (migrate when we need it)
- **Tests:** Vitest + Playwright (Playwright added when there is UI worth testing)
- **Lint/format:** Biome (single tool, no Prettier+ESLint matrix)
- **Package manager:** pnpm
- **CI:** GitHub Actions (wired when a remote repo exists)

Nothing here is a one-way door. Every piece can be swapped before Phase 1 without rewriting business logic.

## Layout

```
.
├── README.md          — this file
├── ENGINEERING.md     — how we work (branching, commits, reviews, CI, intake)
└── .gitignore         — node/next/prisma/editor/OS noise
```

Application scaffolding (`package.json`, `tsconfig.json`, `app/`, `prisma/`) lands at sprint 0 kickoff, once the product thesis picks the first slice to build.

## Getting started

Nothing to run yet. When sprint 0 starts:

```sh
pnpm install
pnpm dev
```

## Workflow

Read `ENGINEERING.md` before opening your first PR.

## Ownership

- **CTO:** @cto (Ayyyanar Tech)
- **Escalation:** @ceo

Work enters the engineering queue via Paperclip — see `ENGINEERING.md` § Intake.
