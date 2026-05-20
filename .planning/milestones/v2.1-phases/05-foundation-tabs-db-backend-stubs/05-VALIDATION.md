---
phase: 5
slug: foundation-tabs-db-backend-stubs
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-18
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Mirrors `05-RESEARCH.md` § Validation Architecture (line 907) into the GSD standard artifact shape.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Frontend framework** | Vitest 4.1.x (existing — confirmed via `frontend/package.json` and `frontend/src/pages/__tests__/`) |
| **Backend framework** | pytest + pytest-asyncio (existing — confirmed via `backend/tests/` and project conventions) |
| **Frontend config file** | `frontend/vite.config.ts` (Vitest reads same config) |
| **Backend config file** | `backend/pyproject.toml` / existing pytest setup |
| **Quick run (frontend)** | `cd frontend && npm run test` |
| **Quick run (backend)** | `cd backend && uv run pytest -x` |
| **Quick run (scheduler boot smoke)** | `cd scheduler && uv run python -c "import worker"` |
| **Migration round-trip** | `cd backend && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic downgrade -1 && uv run alembic upgrade head` |
| **Full suite (Phase 5)** | All three quick runs above, sequentially |
| **Estimated runtime** | ~30s (vitest 8-12s + pytest 5-10s + scheduler boot 1-2s + alembic 8-10s) |

---

## Sampling Rate

- **After every task commit:** Run the appropriate per-task `<automated>` command embedded in each PLAN.md task
- **After every plan wave:** Run the Phase 5 full suite (3 quick-runs sequentially)
- **Before `/gsd:verify-work`:** Full suite must be green and migration round-trip must succeed
- **Max feedback latency:** ~30 seconds end-to-end (longest single command is the 4-step alembic round-trip)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 05-01 | 1 | (Phase 7 pre-req — no Phase 5 REQ) | unit smoke | `cd scheduler && uv run python -c "import worker; assert 1019 in worker.JOB_LOCK_IDS.values()"` | ✅ | ⬜ pending |
| 5-02-01 | 05-02 | 1 | DB-01 | shell (alembic) | `cd backend && uv run alembic upgrade head` (after writing 0011) then `uv run alembic downgrade -1` round-trip | ✅ | ⬜ pending |
| 5-02-02 | 05-02 | 1 | DB-02, DB-05 | shell (alembic) | `cd backend && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic downgrade -1 && uv run alembic upgrade head` (4-step round-trip) | ✅ | ⬜ pending |
| 5-03-01 | 05-03 | 2 | DB-03 (models) | unit | `cd backend && uv run python -c "from app.models.calendar_item import CalendarItem; from app.models.weekly_sweep import WeeklySweep; print(CalendarItem.__tablename__, WeeklySweep.__tablename__)"` | ✅ | ⬜ pending |
| 5-03-02 | 05-03 | 2 | DB-03 (parity) | unit | `cd backend && uv run pytest tests/test_model_parity.py -v` | ❌ W0 | ⬜ pending |
| 5-04-01 | 05-04 | 3 | DB-04 (routers) | unit | `cd backend && uv run python -c "from app.routers.calendar import router; from app.routers.weekly_sweeps import router as wsr"` | ✅ | ⬜ pending |
| 5-04-02 | 05-04 | 3 | DB-04 (auth + 200/401) | integration | `cd backend && uv run pytest tests/test_stubs.py -v` | ❌ W0 | ⬜ pending |
| 5-05-01 | 05-05 | 1 | TAB-01, TAB-02, TAB-03 | typecheck + grep | `cd frontend && npx tsc --noEmit` + acceptance greps in PLAN | ✅ | ⬜ pending |
| 5-05-02 | 05-05 | 1 | TAB-04, TAB-05 | build + grep | `cd frontend && npx tsc --noEmit && npm run build` + AppShell/AppHeader git-diff checks | ✅ | ⬜ pending |
| 5-05-03 | 05-05 | 1 | TAB-02..05 (live UX) | checkpoint:human-verify | Manual browser steps (8 steps in PLAN); no automated command (correct per spec — UX behavior) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Sampling continuity:** No 3 consecutive implementation tasks lack automated verify. Plan 05-05 Task 3 is the only `checkpoint:human-verify` and is correctly excluded from the automated-sampling chain.

---

## Wave 0 Requirements

- [ ] `backend/tests/test_model_parity.py` — asserts `CalendarItem` + `WeeklySweep` are structurally identical between `backend/app/models/` and `scheduler/models/` (table name, column names, column types — specifically `isinstance(c.type, Date)` for the date columns to enforce P2 pitfall prevention). Covers DB-03.
- [ ] `backend/tests/test_stubs.py` — asserts `GET /calendar` and `GET /weekly-sweeps` return `200 OK` with `{"items":[], "total":0}` / `{"sweeps":[], "total":0}` through JWT auth; also asserts `401` when called without auth. Covers DB-04.
- Pytest + Vitest infrastructure is **already present** — no framework installs needed.
- Vitest config inherited from `frontend/vite.config.ts` (no separate `vitest.config.ts` needed).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tab strip renders correctly with active state on `/`, `/calendar`, `/viral` | TAB-02, TAB-03 | Visual presence + active-state styling is a render-level UX concern — Vitest could DOM-assert but human-verify is faster and catches Tailwind class regressions | Visit `/`, confirm "News Funnel" tab highlighted; visit `/calendar`, confirm "Content Calendar" tab highlighted; visit `/viral`, confirm "Weekly Viral Sweeper" tab highlighted |
| Browser Back/Forward updates tab highlight | TAB-03 | P3 pitfall (tab desync) is a behavior emerging from the browser history API + NavLink interaction; reproducing in a headless test requires `happy-dom` + history shimming | Navigate `/` → `/calendar` → browser Back; assert News Funnel tab highlighted (NOT Content Calendar) |
| Tabs do NOT appear on `/digest` or `/settings` | TAB-02 | Visual absence is easier to confirm by sight than by test setup that mounts the full route tree | Visit `/digest` and `/settings`; confirm no tab strip is rendered |
| v2.0 routes `/queue` and `/agents/:slug` still redirect to `/` | TAB-04 (P4 prevention) | Redirect-then-render is testable but the test setup overhead exceeds the value for a single sanity check | Visit `/queue` while authenticated; assert browser URL becomes `/` and News Funnel tab is active |
| Coming-soon stubs render inside the tabbed layout | TAB-02 | Visual presence check | Visit `/calendar` and `/viral`; confirm "Coming soon" text renders inside the same layout as Tab 1 |
| Unauthenticated `/queue` redirects to `/login` | TAB-04 (P4 prevention) | Auth-gate behavior is testable but requires session simulation; faster to confirm visually in an incognito window | Open `/queue` in an incognito window; assert redirect to `/login` (not direct render of `/`) |

All 6 manual checks are bundled into Plan 05-05 Task 3 (the human-verify checkpoint). See PLAN 05-05 for the exact 8-step verification script.

---

## Pitfall → Validation Mapping

| Pitfall | Severity | Validation guard | Where |
|---------|----------|------------------|-------|
| P1 — Alembic `down_revision` mismatch | CRITICAL | `grep -c 'down_revision = "0010"' 0011_*.py == 1` and `grep -c 'down_revision = "0011"' 0012_*.py == 1` | Plan 05-02 acceptance criteria |
| P2 — `Column(DateTime)` instead of `Column(Date)` | CRITICAL | `grep -c "Column(Date, nullable=False)" *.py` (calendar_items×1, weekly_sweeps×2) + `isinstance(c.type, Date)` in parity test | Plans 05-02, 05-03; `test_model_parity.py` |
| P3 — Tab `value` desyncs from URL on Back/Forward | CRITICAL | `grep -c "useState" TabNav.tsx == 0` and `grep -c "defaultValue" TabNav.tsx == 0`; manual browser Back test | Plan 05-05 Tasks 1 + 3 |
| P4 — v2.0 redirect routes lose auth gating after restructure | HIGH | Incognito visit `/queue` → redirect to `/login` (manual); grep for `<ProtectedRoute>` wrapping the redirect block | Plan 05-05 Task 3 step 8 |
| P5 — AppShell/AppHeader accidentally modified | HIGH | `git diff --exit-code frontend/src/components/layout/AppShell.tsx AppHeader.tsx` returns exit 0 | Plan 05-05 Tasks 1 + 2 acceptance |
| P25 — Lock 1019 used outside `JOB_LOCK_IDS` | CRITICAL | `grep -c '"weekly_sweeper": 1019' scheduler/worker.py == 1`; `python -c "import worker"` exits 0 (OPS-02 assertion passes) | Plan 05-01 acceptance |
| P26 — Dual-model parity drift | HIGH | `test_model_parity.py` asserts column names + types match | Plan 05-03 Task 2 |
| P28 — Multiple Alembic heads | CRITICAL | `cd backend && uv run alembic heads` returns exactly one head before 0011 lands | Plan 05-02 Task 1 pre-check |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or `checkpoint:human-verify` (Plan 05-05 Task 3 only)
- [x] Sampling continuity: no 3 consecutive implementation tasks without automated verify (verified above)
- [x] Wave 0 covers all MISSING references (test_model_parity.py + test_stubs.py)
- [x] No watch-mode flags (`pytest -x`, `tsc --noEmit`, `npm run build` are all one-shot)
- [x] Feedback latency < 30s (total full-suite estimate)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-18 (orchestrator — derived directly from 05-RESEARCH.md § Validation Architecture; all coverage already baked into PLAN acceptance criteria by gsd-planner)
