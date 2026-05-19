# Phase 9: Multi-Tenant Foundation - Context

**Gathered:** 2026-05-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Single atomic deploy turning the single-tenant Seva dashboard into a multi-tenant platform supporting Seva + Juno with a company switcher. Phase 9 covers all of TENANT-01..10 and ships every piece needed for `/seva/*` to render byte-equivalent to v2.1, `/juno/*` to render empty-state on all 3 tabs, and one scheduler fire to produce both a Seva (`completed`) and a Juno (`partial`) `daily_summaries` row. Juno's real defence-sector content is **Phase 10**, not Phase 9 — Juno renders empty-states until Phase 10 lands.

Partial multi-tenancy is worse than none — every TENANT-* requirement ships as one deploy.

**Carrying forward from earlier milestones:**

- **v2.1 Phase 5 (D-04, D-05):** `AppShell.tsx` byte-frozen baseline preserved. `AppHeader.tsx` byte-freeze formally lifted in v3.0 with documented rationale (Phase 9 Decision D-02 below).
- **v2.1 Phase 7 (D-14, D-15):** APScheduler advisory-lock uniqueness (OPS-02) preserved. Current keys: `midday_digest=1005`, `daily_summary=1017`, `daily_summary_prune=1018`, `weekly_sweeper=1019`. Phase 9 adds 2 (D-01 below).
- **v2.1 Phase 8 (D-05, D-06):** Semantic CSS tokens `--color-brand-accent[-hover/-subtle]` added to `index.css` `@theme inline`; zinc-* untouched. CompanySwitcher uses these semantic tokens (D-08 below), NOT literal `amber-500`/`amber-400`.
- **v2.1 Phase 8 (D-07):** `scheduler/agents/content/` directory removed; lock IDs 1010-1016 freed. The next-free integer block above 1019 starts at 1020 — used by D-01 below.

**Research input:** `.planning/research/{STACK,FEATURES,ARCHITECTURE,PITFALLS,SUMMARY}.md` from 2026-05-19. Three inter-research disagreements were flagged for this discuss-phase — all three resolved below (D-01, D-02, D-03).

</domain>

<decisions>
## Implementation Decisions

### Scheduler Topology (Disagreement 1 — RESOLVED)
- **D-01:** **Per-company jobs with explicit lock IDs (Approach B from research SUMMARY.md).** Add two entries to `JOB_LOCK_IDS` in `scheduler/worker.py`: `juno_daily_summary=1020` AND `juno_weekly_sweeper=1021`. Both slots reserved in Phase 9; `juno_daily_summary` is **registered** as an APScheduler job in Phase 9; `juno_weekly_sweeper` is the **slot only** (registered later in v3.1+ when Juno Sweeper lands). Each Juno job gets its own `add_job(..., args=[company_id])` factory mirroring `_make_daily_summary_job`. OPS-02 advisory-lock uniqueness assertion preserved and unchanged in structure.
- **D-01a:** **5-minute stagger between Seva and Juno fires.** Seva `daily_summary` stays at 07:00 PT (existing). Juno `daily_summary` fires at 07:05 PT. Rationale: spreads Anthropic API rate-limit pressure (PITFALLS.md §3 — Anthropic rate-limit collision); avoids simultaneous Sonnet calls; both finish well before the operator's morning. APScheduler `CronTrigger(day_of_week='mon-sun', hour=7, minute=5, timezone='America/Los_Angeles')` for Juno.
- **D-01b:** **Per-company independent failure mode.** A Seva failure does NOT block Juno from firing (and vice versa). Each tenant's job has its own try/except + its own `agent_runs` row + its own `daily_summaries` row write. Result: one APScheduler fire writes 0, 1, or 2 `daily_summaries` rows depending on per-company success.

### AppHeader Freeze Treatment (Disagreement 2 — RESOLVED)
- **D-02:** **Path A — Lift the Phase 5 byte-freeze formally with documented v3.0 rationale.** Surgical 5-line insert of `<CompanySwitcher />` inside `frontend/src/components/layout/AppHeader.tsx` between the brand mark `<div>` and the Logout `<button>`. AppHeader becomes the canonical home for the switcher, matching Linear/Notion/Slack/Vercel convention. The v3.0 baseline becomes the new locked contract going forward; v2.1 visual QA baseline is re-baselined at Phase 9 verification.
  - Document the freeze-lift in: (a) Phase 9 SUMMARY.md "Decisions" section, (b) inline `// v3.0 freeze-lift (Phase 9) — see 09-CONTEXT.md D-02` comment above the modified region, (c) `.planning/PROJECT.md` Key Decisions.
- **D-02a:** **Brand mark + wordmark stay "Seva Mining" on both tenants in v3.0.** Per-company branding is explicitly deferred to v3.1+ per `REQUIREMENTS.md → TENANT-BRAND-v31`. Operator sees the "S" amber square + "Seva Mining" wordmark even when viewing `/juno/`. Accepted v3.0 tech debt; documented in CONTEXT.md, REQUIREMENTS.md, and Phase 9 SUMMARY.md. v3.1 phase will introduce per-company brand-mark + wordmark + (eventually) per-company color palette.

### Tenant ID Source of Truth (Disagreement 3 — RESOLVED)
- **D-03:** **Hardcoded CHECK constraint + Python Literal (Approach A from research SUMMARY.md).** Alembic 0014 adds `CHECK company_id IN ('seva', 'juno')` to all three multi-tenant tables (`daily_summaries`, `calendar_items`, `weekly_sweeps`). `ACTIVE_COMPANIES: Literal["seva", "juno"]` lives in `backend/app/companies/__init__.py` (and mirrored in `scheduler/companies/__init__.py` for the scheduler-side import path). NO `companies` DB table in v3.0.
  - Tech debt accepted: close in v3.2+ when N>2 tenants requires a `companies` table. Tracked in `REQUIREMENTS.md → TENANT-N-v32`. v3.0 explicitly does NOT scale to N=3 in production without a code deploy.

### URL + Redirect + Switcher UX
- **D-04:** **Short tenant slugs.** URLs are `/seva/...` and `/juno/...` (NOT `/seva-mining/...` or `/juno-industries/...`). Slugs MUST match `^[a-z][a-z0-9-]{1,19}$` regex (lowercase letters + digits + hyphens; 2-20 chars). Path parameter is `:company` in React Router and `{company}` in FastAPI.
- **D-05:** **Bare `/` redirects to `/seva/` (hardcoded — NOT last-visited).** Simplest behavior. Last-visited persistence is deferred to v3.1+ — Zustand `persist` middleware will still store "last visited tenant" as a free byproduct of the switch action (D-08), but the bare `/` redirect ignores it for v3.0. Open path to a v3.1+ "last-visited landing" feature without re-architecture.
- **D-06:** **v2.x bookmark grace redirect — auto-prefix to `/seva/`.** All unprefixed legacy URLs auto-redirect to the Seva tenant:
  - `/` → `/seva/`
  - `/calendar` → `/seva/calendar`
  - `/viral` → `/seva/viral`
  - `/queue` → `/seva/` (legacy v2.0 redirect target preserved)
  - `/agents/:slug` → `/seva/` (legacy v2.0 redirect target preserved)
  - `/digest`, `/settings`, `/login` → unchanged (these are NOT tenant-scoped routes per Phase 5 baseline; they stay at root level)
  - Implementation: React Router `<Navigate>` elements at the `/calendar`, `/viral`, `/`, `/queue`, `/agents/:slug` route definitions. NO 404 for legacy bookmarks.
- **D-07:** **`CompanySwitcher` visual style: segmented control.** Two side-by-side buttons (Seva | Juno) with `border-zinc-800` baseline + active state `border-brand-accent text-brand-accent`. Uses semantic CSS tokens from v2.1 Phase 8 (`--color-brand-accent[-hover/-subtle]`), NOT literal `amber-500`. Active state derived from `useParams<{company: string}>()` — URL is canonical (per ARCHITECTURE.md D-03). Switching companies fires a `navigate(`/${nextCompany}${currentSubPath}`)` to preserve the user's current tab when switching tenants (e.g. switching from `/seva/calendar` → `/juno/calendar`, NOT `/juno/`).
- **D-08:** **TanStack Query cache invalidation on switch.** Switching tenants calls `queryClient.clear()` as defence-in-depth against any query key that forgot to include `company_id`. Also, every query key gains a `company_id` slot via a centralized factory at `frontend/src/api/queryKeys.ts` (PITFALLS.md HIGH — TanStack stale render).

### Claude's Discretion (planner picks)
- **Login post-auth redirect target.** After successful login, where does the operator land? Default: hardcoded `/seva/` (matches D-05). Planner may instead route to last-visited if the `intended URL` (the URL the operator tried to access pre-login) was a tenant-scoped URL — this is the standard "intended destination" pattern that already exists in the v2.x `<ProtectedRoute>`. Either is fine; matching the existing `<ProtectedRoute>` behavior is recommended.
- **Tab state preservation across company switch.** When operator switches `/seva/calendar` → `/juno/`, does the active tab carry over (so they land on `/juno/calendar`) or do they land on `/juno/` index? D-07 says "preserve the user's current tab" (sub-path) — but the planner picks the exact behavior when the sub-path is something Juno doesn't have content for yet (e.g. switching to `/juno/viral` lands on the empty-state, which is fine).
- **`scheduler/companies/juno/` module skeleton in Phase 9.** The Juno daily_summary cron MUST be registered + fire-able in Phase 9 (writes a `status='partial'` row with empty section markdown). The planner picks whether to ship a minimal `scheduler/companies/juno/{feeds.py, prompts.py, serpapi.py}` skeleton in Phase 9 (with empty lists + no-op Sonnet call returning canned partial markdown) OR write directly to the DB with all-empty sections + a hardcoded "Coming in Phase 10" status note. Recommended: minimal skeleton (~30 lines) so Phase 10 is purely "fill the lists." The 5-min stagger means the empty Juno cron can be active in production without breaking anything.
- **CI grep gate implementation.** Recommended: shell script at `scripts/verify-tenant-isolation.sh` mirroring the v2.1 grep verification scripts. Grep for `select(DailySummary)` / `select(CalendarItem)` / `select(WeeklySweep)` outside `backend/app/queries/scoped.py` (and `backend/app/queries/__init__.py` if re-exports happen). Wired into Wave 0 of the plan. Planner picks exact regex + exit code wiring.
- **Zustand `persist` middleware key naming.** `lastVisitedCompany` (camelCase Zustand convention) stored under localStorage key `seva-mining-app-state-v3` (the existing app-store key) — i.e. add to the existing Zustand store, don't create a new persist target.

### Folded Todos
None — no pending todos matched Phase 9 scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Domain & Architecture
- `.planning/research/SUMMARY.md` — research synthesis with all 3 disagreements explicit (each disagreement resolved by D-01/D-02/D-03 in this CONTEXT.md)
- `.planning/research/ARCHITECTURE.md` — full file-change map (NEW / MODIFIED / UNCHANGED) and 5 architectural decisions
- `.planning/research/STACK.md` — multi-tenancy strategy rejection of fastapi-tenancy / RLS / schema-per-tenant; Sonnet structured outputs for Phase 10
- `.planning/research/FEATURES.md` — feature decomposition (Multi-tenancy / Juno News Funnel / World Events) + table-stakes vs differentiator vs anti-feature
- `.planning/research/PITFALLS.md` — full pitfall taxonomy (cross-tenant leak, ContextVar leak, backfill race, AppHeader freeze, bookmark breakage, etc.)

### Requirements
- `.planning/REQUIREMENTS.md` §"Multi-Tenant Foundation (TENANT)" — TENANT-01..10 full text; each requirement maps to exactly one Phase 9 plan via roadmapper assignment

### v2.x Carry-Forward
- `.planning/phases/05-foundation-tabs-db-backend-stubs/05-CONTEXT.md` — AppShell + AppHeader freeze original declaration
- `.planning/phases/07-weekly-viral-sweeper/07-CONTEXT.md` — D-14 (CronTrigger), D-15 (idempotency guard), D-16 (status mapping) — Juno daily_summary cron mirrors these
- `.planning/phases/08-ui-polish-dead-code-strip/08-CONTEXT.md` — D-05 (semantic CSS tokens added to `index.css` `@theme inline`); CompanySwitcher uses these
- `.planning/milestones/v2.1-research/` — archived v2.1 research artifacts (do NOT confuse with active v3.0 `.planning/research/`)

### Backend Surfaces (Phase 9 edit targets)
- `backend/app/main.py` — router registration; will gain `/api/{company}/` prefix
- `backend/app/models/{daily_summary,calendar_item,weekly_sweep}.py` — add `company_id` column (dual-model parity per Phase 5 D-03)
- `scheduler/models/{daily_summary,calendar_item,weekly_sweep}.py` — mirror dual-model parity
- `backend/app/routers/{summaries,calendar,weekly_sweeps}.py` — switch to `scoped_*()` query helpers + `get_current_company()` dependency
- `backend/alembic/versions/` — new `0014_add_company_id.py` with backfill in same transaction
- `scheduler/worker.py` — `JOB_LOCK_IDS` gains 1020 + 1021; OPS-02 assertion preserved; new `_make_juno_daily_summary_job` factory
- `scheduler/agents/daily_summary.py` — refactor to take `company_id` param; or split into `_run_daily_summary_for_company(session, company_id)` function

### Frontend Surfaces (Phase 9 edit targets)
- `frontend/src/App.tsx` — `<Route path=":company">` wrapper around `<TabbedDashboard />`; bookmark grace `<Navigate>` elements per D-06
- `frontend/src/components/layout/AppHeader.tsx` — FREEZE LIFTED — 5-line CompanySwitcher insert per D-02
- `frontend/src/components/layout/AppShell.tsx` — UNCHANGED (Phase 5 baseline preserved)
- `frontend/src/components/layout/TabbedDashboard.tsx` — may need to read `:company` from `useParams` to pass to nested pages
- `frontend/src/components/layout/TabNav.tsx` — `<NavLink>` to includes use `/${company}/calendar` etc. instead of just `/calendar`
- `frontend/src/components/layout/CompanySwitcher.tsx` (NEW) — segmented control per D-07
- `frontend/src/api/queryKeys.ts` (NEW) — TanStack key factory per D-08
- `frontend/src/stores/` — Zustand store gets `lastVisitedCompany` field with `persist` middleware
- `frontend/src/pages/*.tsx` — each page reads `:company` from `useParams` and passes to query keys + API client

### Testing
- `backend/tests/test_multitenant_isolation.py` (NEW) — TENANT-10 deliverable; cross-tenant leak detection
- `scripts/verify-tenant-isolation.sh` (NEW, Wave 0) — CI grep gate per Claude's-discretion note above

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`AppHeader.tsx`** — 30 lines, simple flex layout. Adding a `<CompanySwitcher />` is a 5-line insert. Brand mark + Logout structure stays as-is.
- **`<Navigate>` from React Router v6** — already used in v2.x for bookmark redirects (`/queue → /`, `/agents/:slug → /`). Phase 9 extends this pattern for `/calendar → /seva/calendar` etc.
- **`useParams` hook** — already standard React Router v6 idiom. New `useParams<{company: string}>()` reads at every nested route.
- **`useAppStore` Zustand store with `persist` middleware** — already exists. Add `lastVisitedCompany` field; persist key reused.
- **APScheduler `_make_daily_summary_job` factory** — Phase 5 / Phase 7 pattern. `_make_juno_daily_summary_job` mirrors it 1:1 with `company_id='juno'` injected.
- **`agent_runs` table** — already has `notes JSONB` column for per-job metadata. v3.0 stores `{"company_id": "juno"}` in `notes` (NOT a new column — D-08 from ARCHITECTURE.md).
- **`status='partial'` row pattern** — established by Phase 7. Juno daily_summary with empty sections writes `status='partial'` until Phase 10 populates real content.
- **Semantic CSS tokens `--color-brand-accent[-hover/-subtle]`** — added in v2.1 Phase 8. CompanySwitcher uses these.

### Established Patterns
- **Dual-model SQLAlchemy parity** (Phase 5 D-03) — every multi-tenant table edit happens in BOTH `backend/app/models/` AND `scheduler/models/`. `company_id` column addition follows the same dual edit pattern.
- **Pydantic v2 schemas** — `from_attributes=True` ORM serialization (Phase 7 D-01). Response schemas may add `company_id` field (TBD by planner — recommended yes for debugging).
- **Atomic Alembic migrations** — backfill happens in the same transaction as the `ADD COLUMN` (Phase 5 D-02 / Phase 7 patterns). 0014 must follow this discipline.
- **`/login` and `/digest` and `/settings` are NOT tenant-scoped** — these stay at root. Tenant-scoping applies only to `/seva/...` and `/juno/...` (and the legacy v2.x paths that grace-redirect into them).

### Integration Points
- Router prefix change in `backend/app/main.py`: `/calendar` → `/api/{company}/calendar`, `/summaries` → `/api/{company}/summaries`, `/weekly-sweeps` → `/api/{company}/weekly-sweeps`. `auth` router stays at `/api/auth` (NOT tenant-scoped).
- Frontend API client base URL pattern: `apiFetch(`/api/${company}/calendar`, ...)`. Centralize the company-prefix concat in `frontend/src/api/client.ts`.
- New shadcn primitive: **none needed**. Segmented-control switcher uses existing `<button>` elements with Tailwind utility classes. No `npx shadcn add` calls in Phase 9.

</code_context>

<specifics>
## Specific Ideas

- **5-min stagger** between Seva (07:00 PT) and Juno (07:05 PT) daily_summary fires. Future Juno Weekly Viral Sweeper (Phase 11+) will use Sunday 08:05 PT (5-min stagger from Seva's 08:00 PT).
- **Lock ID slot reservation** — `juno_weekly_sweeper=1021` reserved in Phase 9's `JOB_LOCK_IDS` even though the Sweeper job is not registered until v3.1+. Saves a future surgical edit; preserves OPS-02 inventory clarity.
- **CompanySwitcher segmented control** matches the existing Linear-style amber/zinc design language (Phase 8 D-05 semantic tokens). NOT a dropdown, NOT a Cmd+K palette — segmented is the visually-cleanest pattern for N=2.
- **Tab preservation on switch** — switching from `/seva/calendar` → Juno preserves the calendar tab (lands on `/juno/calendar` empty-state), not Juno's index. Operator's mental model stays "I'm on the calendar tab; just different company now."

</specifics>

<deferred>
## Deferred Ideas

- **Per-company branding** (logos, color palettes, wordmark) — TENANT-BRAND-v31. v3.0 keeps "Seva Mining" wordmark on both tenants.
- **`companies` DB table** — TENANT-N-v32. v3.0 uses hardcoded CHECK + Python Literal. Migration path documented in D-03.
- **Last-visited tenant for bare `/` redirect** — v3.1+ enhancement on top of the Zustand `lastVisitedCompany` field that v3.0 already populates as a byproduct.
- **Per-tenant Anthropic API key** — PITFALLS.md §5 recommendation; defer to v3.1+ unless Anthropic content-policy review surfaces a real need in Phase 10.
- **Cmd+K command palette for tenant switching** — v3.1+ if power-user UX warrants it. v3.0 segmented control covers the N=2 case.
- **Per-company RBAC / user permissions** — TENANT-RBAC-v32. Single-operator model continues through v3.0.
- **Real Juno content** (Defence News + Canadian Procurement + World Events sections) — Phase 10 (DEF-01..10).
- **Juno Calendar (Tab 2) + Juno Weekly Viral Sweeper (Tab 3)** — JUNO-CAL-v31 + JUNO-SWEEP-v31. v3.0 renders empty-states on these tabs.

### Reviewed Todos (not folded)
None — no pending todos matched Phase 9 scope.

</deferred>

---

*Phase: 09-multi-tenant-foundation*
*Context gathered: 2026-05-19*
