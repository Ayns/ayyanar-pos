# Engineering Workflow — Ayyyanar Tech

How we ship. Single-engineer team today (CTO). Rules are deliberately thin; tighten them only when a real incident demands it.

## Principles

1. **Boring beats novel.** Pick the tool most engineers already know.
2. **Two-way doors only.** Any one-way door (domain, paid service, external integration, data migration) requires CEO sign-off first.
3. **Small PRs, shipped daily.** A PR that has not merged in two working days is a process failure, not a code failure.
4. **Every change is reviewable.** If there is no peer reviewer, self-review the diff out loud in the PR description before merging.

## Branching

- **Default branch:** `main`. Always deployable.
- **Feature branches:** `<kind>/<ticket>-<slug>` — e.g. `feat/AYY-12-signup-form`, `fix/AYY-34-login-500`, `chore/AYY-9-bump-node`.
- **Kinds:** `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `infra`, `spike`.
- **No long-lived branches.** Rebase on `main` daily. Delete after merge.

## Commits

- [Conventional Commits](https://www.conventionalcommits.org/) for subject: `feat(auth): add magic-link sign-in`.
- Subject ≤ 72 chars, imperative mood, no trailing period.
- Body (optional) explains the *why* — not the *what*. The diff already shows the what.
- Every commit that maps to a Paperclip issue must reference it: `Refs: AYY-12` or `Closes: AYY-12`.
- Commits that touch infra, data shape, or external contracts must have a body.

## Pull requests

- **Title** = conventional-commit-style summary.
- **Body** template:
  ```
  ## What
  One paragraph. What changes after this merges?

  ## Why
  Link the issue. Call out the trade-off or alternative considered.

  ## Risk
  What could break? How will we know? Rollback plan.

  ## Verification
  How I tested. Screenshots / logs / command output when relevant.
  ```
- **Size target:** < 400 added/changed LOC. Split if larger, unless it is a pure rename/move.
- **Draft early.** Open a draft PR as soon as tests go green locally; use it as a working log.

## Review bar

Until a second engineer joins, the review bar is:

1. **Self-review required.** Before marking ready, read your own diff top-to-bottom in the GitHub UI and leave at least one comment per non-trivial decision.
2. **CEO review for "two-way door" violations only.** Normal code changes do not need CEO sign-off.
3. **Tests gate merge.** CI must be green. No merges with failing or skipped tests.
4. **No merge on Fridays after 15:00 local.** Deploy Monday instead.

Once a second engineer is hired, reviews become mandatory and `main` gets branch protection.

## CI expectations

GitHub Actions wires up once the repo has a remote. Required checks, in order:

1. `typecheck` — `tsc --noEmit`.
2. `lint` — `biome check .`.
3. `test` — `vitest run`.
4. `build` — `next build` (or framework equivalent).

CI must finish in < 5 minutes at Phase 0 scale. If it creeps past 5 minutes, cut something before adding more.

## Environments

- **`local`** — SQLite, `.env.local`, default for all development.
- **`preview`** — per-PR ephemeral env once we have a hosting target picked.
- **`prod`** — single region, single instance until we have paying users.

No staging environment at Phase 0. Previews + prod is enough.

## Secrets

- Never commit secrets. `.env*` is gitignored (except `.env.example`).
- `.env.example` is the authoritative list of env vars the app reads. Update it in the same PR that adds the variable.

## Definition of done (per change)

A change is done when:

- [ ] Code merged to `main`.
- [ ] Paperclip issue is `done` or `in_review` with a comment linking the PR.
- [ ] Docs updated if behavior visible to users, operators, or other engineers changed.
- [ ] Telemetry / logs exist for the new code path (once we have a logging solution).

## Intake

How work enters the engineering queue. One system: Paperclip issues.

| Source | Channel | Action |
| ------ | ------- | ------ |
| CEO | Direct assign to CTO agent | Picked up on next heartbeat. |
| Board | Comment with `@cto` on a Paperclip issue, or direct assign | CTO triages, estimates, sets status. |
| CTO (self) | Create issue under the current project, assign to self | Used for proactive work and breaking down features. |
| External bug report | Board forwards to CTO as a new issue | CTO labels + triages. |

### Labels

- `kind/bug`, `kind/feature`, `kind/chore`, `kind/infra`, `kind/spike`, `kind/docs`
- `area/api`, `area/web`, `area/data`, `area/infra`
- `pri` inherits from Paperclip priority (`critical` / `high` / `medium` / `low`) — do not shadow it with a label.

### Triage cadence

- **Daily (CTO):** scan inbox at start of heartbeat. Anything `todo` or `in_progress` assigned to me moves first.
- **Weekly (CTO, Monday):** skim the backlog, re-prioritize, kill stale tickets. Set up as a Paperclip routine on Phase 0 exit.

### SLAs (self-imposed)

| Priority | First response | Target resolution |
| -------- | -------------- | ----------------- |
| `critical` | Same heartbeat | 24 h |
| `high`     | Same day | 3 business days |
| `medium`   | 2 business days | 2 weeks |
| `low`      | Weekly triage | Best-effort |

### `@mentions`

Use `@cto` in comments only for urgent or ambiguous items (they cost budget by triggering heartbeats). For routine status updates and handoffs, prefer direct assignment or status changes — those trigger wakes too, without the mention cost.

## When this doc is wrong

Open a PR with the change. These rules exist to move fast, not to preserve themselves. Update them whenever reality contradicts them.
