---
phase: 09-multi-tenant-foundation
plan: 02
subsystem: backend-db-foundation
tags: [alembic, postgres, sqlalchemy, multi-tenant, dual-model-parity, scoped-queries, fastapi-deps, tenant-isolation]

# Dependency graph
requires:
  - phase: 09-multi-tenant-foundation
    plan: 01
    provides: 12 Wave 0 RED test scaffolds (backend test_migration_0014.py, test_queries_scoped.py, test_model_parity.py extension) + CI grep gate
provides:
  - Alembic 0014 migration applied to Neon (alembic_version = 0014_add_company_id)
  - backend/app/companies/__init__.py — CompanyId Literal + ACTIVE_COMPANIES tuple (D-03 source of truth)
  - backend/app/queries/{__init__.py, scoped.py} — scoped_summaries / scoped_calendar / scoped_weekly_sweeps Select-returning helpers
  - get_current_company FastAPI dependency in app/dependencies.py (404 on unknown slug, 422 on slug-regex miss)
  - company_id Mapped column on ALL 6 dual-model files (backend + scheduler × 3 tables)
  - postgres_migration_session pytest fixture in conftest.py for PG-specific schema tests
affects: [09-03-PLAN.md, 09-04-PLAN.md, 09-05-PLAN.md]

# Tech tracking
tech-stack:
  added: []  # no new deps — uses existing alembic, sqlalchemy 2.x, fastapi, pytest, asyncpg
  patterns:
    - "Alembic expand-step pattern with `server_default='seva'` in same `op.add_column(...)` ALTER — eliminates HIGH-3 backfill race by leveraging Postgres DEFAULT in the DDL transaction (no separate UPDATE step needed)"
    - "Naming-convention-aware constraint creation: pass the *short* constraint_name token (e.g. 'company_id') and let MetaData's naming_convention prefix produce the full name (e.g. 'ck_daily_summaries_company_id'); pre-prefixing causes double-prefix bug"
    - "Postgres-real test fixture pattern: capture real DATABASE_URL in conftest BEFORE SQLite override; expose `postgres_migration_session` fixture that skips on SQLite-only environments and rolls back per test for hermetic schema-introspection tests"
    - "Scoped query helper module: `select(Model).where(Model.company_id == company_id)` factory functions return SQLAlchemy `Select` so callers compose .order_by()/.limit() and execute via the existing AsyncSession; CI grep gate forbids raw `select(Model)` outside the helper module"
    - "Path-prefix tenant dependency: `Path(..., pattern=...)` for slug-shape validation (regex 422) + ACTIVE_COMPANIES membership check (404); returns the slug typed as `Literal['seva','juno']` so downstream callers (scoped_*) get type-narrowed access"

key-files:
  created:
    - backend/app/companies/__init__.py
    - backend/alembic/versions/0014_add_company_id.py
    - backend/app/queries/__init__.py
    - backend/app/queries/scoped.py
  modified:
    - backend/app/dependencies.py
    - backend/app/models/daily_summary.py
    - backend/app/models/calendar_item.py
    - backend/app/models/weekly_sweep.py
    - scheduler/models/daily_summary.py
    - scheduler/models/calendar_item.py
    - scheduler/models/weekly_sweep.py
    - backend/tests/conftest.py
    - backend/tests/test_migration_0014.py
    - backend/tests/test_model_parity.py
    - backend/tests/test_queries_scoped.py

key-decisions:
  - "Pass constraint_name=`'company_id'` (short token) to `op.create_check_constraint()` and `op.drop_constraint()`. The base Metadata's `NAMING_CONVENTION['ck'] = 'ck_%(table_name)s_%(constraint_name)s'` is applied automatically, producing `ck_<table>_company_id`. The first migration attempt pre-prefixed with `f'ck_{table}_company_id'`, causing Postgres to materialize the double-prefixed name `ck_<table>_ck_<table>_company_id` — downgrade was symmetric, so round-trip masked the bug. Fixed by passing the bare token. Test `test_check_constraint` now confirms via pg_get_constraintdef()."
  - "Add a `postgres_migration_session` pytest fixture in conftest.py to support Wave 0 RED tests that query PG-specific catalogs (`information_schema.columns`, `pg_catalog.pg_constraint`, `pg_catalog.pg_indexes`). The conftest captures `os.environ['DATABASE_URL']` BEFORE force-overriding it to SQLite-in-memory; the fixture skips at collection time when only the SQLite URL is available (CI without Neon creds). This was a deviation Rule 1 fix — the Wave 0 tests had been written against PG SQL but bound to the SQLite-only `async_db_session` fixture."
  - "Update each multi-tenant model's `__table_args__` to mirror the index/UNIQUE state produced by migration 0014 — so SQLAlchemy's expected schema matches the actual DB. Specifically: replace `ix_daily_summaries_generated_at`/`ix_weekly_sweeps_generated_at` with composite `ix_*_company_generated (company_id, generated_at DESC)`; replace `ix_calendar_items_date`/`uq_calendar_items_date` with composite `ix_calendar_items_company_date (company_id, date)` + `uq_calendar_items_company_date (company_id, date)`. Done identically on both backend and scheduler sides to preserve `test_model_parity` invariants."
  - "Keep column declaration style consistent with existing models: legacy `Column(String(20), nullable=False, server_default='seva')` (NOT SQLAlchemy 2.x `Mapped[str] = mapped_column(...)`). The model files all use legacy `Column` shape and switching styles mid-file would harm consistency and bloat the diff. Plan called for `Mapped[str]` shape in interfaces but the actual existing style is `Column`; preferred existing-style consistency over plan-text literalness — both shapes are valid SQLAlchemy 2.x."

patterns-established:
  - "Expand-step migration with atomic backfill: `op.add_column(table, sa.Column(name, type, nullable=False, server_default=<value>))` lets Postgres apply the default in the same DDL transaction — no separate UPDATE backfill needed."
  - "Naming-convention-aware constraint naming: when the project's MetaData has `naming_convention`, pass the *short* constraint_name token; never pre-prefix."
  - "Postgres-real test fixture: capture DATABASE_URL pre-override + skip-on-SQLite for tests that query Postgres catalogs."
  - "Scoped query helper module with CI grep gate: `select(Model).where(Model.tenant_col == tenant_id)` factories — the only allowed call sites for raw selects against multi-tenant tables."

requirements-completed: [TENANT-01, TENANT-02, TENANT-03, TENANT-04]

# Metrics
duration: 9m
completed: 2026-05-19
---

# Phase 9 Plan 2: DB Foundation + Scoped Helpers + Companies Module Summary

**Alembic 0014 lands the multi-tenant DB foundation (atomic ADD COLUMN with `server_default='seva'` + CHECK + composite indexes) on all 3 tenant-scoped tables; dual-model parity established (backend + scheduler ORMs); scoped query helpers + `get_current_company` FastAPI dep available for Wave 2 router wiring. All Wave 0 backend RED tests (test_migration_0014, test_queries_scoped, test_daily_summary_parity) flipped GREEN.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-05-19T22:47:46Z
- **Completed:** 2026-05-19T22:56:48Z
- **Tasks:** 3
- **Files modified:** 15 (4 created + 11 modified)

## Accomplishments

- Migration 0014 applied to Neon Postgres; `alembic current` reports `0014 (head)`; round-trip (`downgrade -1` → `upgrade head`) clean.
- All 3 multi-tenant tables carry `company_id VARCHAR(20) NOT NULL DEFAULT 'seva'` with `ck_<table>_company_id` CHECK enumerating `('seva','juno')` and composite indexes leading with `company_id`.
- Existing 12 daily_summaries rows on Neon backfilled to `'seva'` atomically via the DEFAULT; no NULL or stray values found post-migration.
- CHECK constraint verified to reject bogus values (e.g. `INSERT ... company_id='bogus'` raises IntegrityError).
- Dual-model parity: backend + scheduler ORMs both expose the new `company_id` column on DailySummary/CalendarItem/WeeklySweep; `test_model_parity.py` 5/5 GREEN.
- `scoped_summaries`, `scoped_calendar`, `scoped_weekly_sweeps` exported from `backend/app/queries`; each returns a `Select` whose compiled SQL contains the `company_id` filter (4/4 compile assertions GREEN).
- `get_current_company` FastAPI dep available; will be wired into router prefixes in Wave 2.
- CI grep gate (`scripts/verify-tenant-isolation.sh`) still EXIT 0 — Wave 1 added the scoped helpers without touching routers, so the `PRE_WAVE_2_WHITELIST` continues to cover the 5 pre-existing call sites.
- No frontend or scheduler-job edits — Wave 1 scope held to DB + helpers + companies module.
- No regressions: backend 165 PASS (was 156 + 4 new migration + 4 new scoped + 1 newly-green daily_summary parity = 165), scheduler 264 PASS.

## Task Commits

Each task was committed atomically on the working repo's `main` branch (no phase branch — config `branching_strategy: none`).

1. **Task 1: backend/app/companies + Alembic 0014 migration** — `b836714` (feat)
   - 4 files: backend/app/companies/__init__.py + backend/alembic/versions/0014_add_company_id.py + backend/tests/conftest.py + backend/tests/test_migration_0014.py
   - Migration applied + round-tripped on Neon; 4 migration tests GREEN.

2. **Task 2: Dual-model parity — company_id on backend + scheduler ORMs** — `6e11fa2` (feat)
   - 7 files: 6 model files (3 backend × 3 + 3 scheduler × 3) + test_model_parity.py
   - 5 parity tests GREEN; 161 backend + 264 scheduler tests PASS.

3. **Task 3: scoped query helpers + get_current_company dep** — `3cae047` (feat)
   - 4 files: backend/app/queries/__init__.py + backend/app/queries/scoped.py + backend/app/dependencies.py + backend/tests/test_queries_scoped.py
   - 4 scoped-query tests GREEN; CI grep gate EXIT 0; 165 backend tests PASS.

**Plan metadata commit:** (final commit after this SUMMARY.md is written)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Wave 0 test_migration_0014.py was bound to the SQLite-only async_db_session fixture but issued Postgres-specific SQL**

- **Found during:** Task 1 (first attempt at running test_migration_0014.py after removing module-level skip)
- **Issue:** Wave 0 had written test queries against `information_schema.columns`, `pg_catalog.pg_constraint`, `pg_catalog.pg_indexes` — all Postgres-only catalogs. The existing `async_db_session` fixture forces the SQLite-in-memory test URL, so these queries failed (e.g. `column_default` shape differs; `pg_catalog` doesn't exist in SQLite).
- **Fix:** Added a new `postgres_migration_session` fixture in `backend/tests/conftest.py` that:
  1. Captures the real `DATABASE_URL` from the env or `backend/.env` BEFORE conftest forces the SQLite override.
  2. Skips at collection time when only the SQLite URL is available (CI without Neon creds — preserves CI green for tests that don't need real PG).
  3. Connects via asyncpg + `ssl=True` connect-arg (Neon idiom, mirrors `backend/alembic/env.py`).
  4. Rolls back the session in the finalizer so test inserts don't persist between runs.
  5. Refactored test_migration_0014.py to use the new fixture.
- **Files modified:** backend/tests/conftest.py, backend/tests/test_migration_0014.py
- **Commit:** b836714

**2. [Rule 1 - Bug] Alembic constraint naming double-prefix (caught by test_check_constraint)**

- **Found during:** Task 1, between migration apply and test_check_constraint failing
- **Issue:** First version of migration 0014 used `op.create_check_constraint(f"ck_{table}_company_id", ...)`. Combined with the project's MetaData `naming_convention = {"ck": "ck_%(table_name)s_%(constraint_name)s"}`, this produced the double-prefixed actual name `ck_daily_summaries_ck_daily_summaries_company_id`. The downgrade was symmetric so the round-trip succeeded — but the test querying `pg_get_constraintdef(oid)` by the *expected* name `ck_daily_summaries_company_id` returned no row.
- **Fix:** Pass the short token `"company_id"` to both `op.create_check_constraint(...)` and `op.drop_constraint(...)`; let the naming convention add the `ck_<table>_` prefix. Verified via `pg_constraint` query that final names are `ck_daily_summaries_company_id` / `ck_calendar_items_company_id` / `ck_weekly_sweeps_company_id`. Re-ran upgrade/downgrade/upgrade cleanly.
- **Files modified:** backend/alembic/versions/0014_add_company_id.py
- **Commit:** b836714 (same task — fix landed before commit)

**3. [Rule 2 - Critical Functionality] Model `__table_args__` index/UNIQUE state mirrored migration 0014**

- **Found during:** Task 2 (writing dual-model parity)
- **Issue:** Plan called for adding the `company_id` column on each model, but the existing models' `__table_args__` still declared the *old* single-column indexes (`ix_daily_summaries_generated_at`, `ix_weekly_sweeps_generated_at`, `ix_calendar_items_date`, `uq_calendar_items_date`) — which migration 0014 dropped. Leaving the stale indexes in the ORM would (a) drift from DB reality and (b) cause `test_calendar_item_parity` to flag the missing composite UNIQUE.
- **Fix:** Updated `__table_args__` on all 6 multi-tenant model files (backend + scheduler) to declare the composite indexes/uniques produced by migration 0014: `ix_*_company_generated (company_id, generated_at DESC)` and `ix_calendar_items_company_date (company_id, date)` + `uq_calendar_items_company_date (company_id, date)`. Imported `text` where needed for the `DESC` ordering hint.
- **Files modified:** All 6 model files (backend/app/models/{daily_summary,calendar_item,weekly_sweep}.py + scheduler/models/{daily_summary,calendar_item,weekly_sweep}.py)
- **Commit:** 6e11fa2

**4. [Rule 2 - Critical Functionality] Plan specified `Mapped[str]` style; existing models use legacy `Column(...)` style**

- **Found during:** Task 2 (reading the existing model files)
- **Issue:** Plan interfaces in `09-02-PLAN.md` and the research code-example showed `company_id: Mapped[str] = mapped_column(String(20), nullable=False, server_default="seva")` (SQLAlchemy 2.x typed style). But every existing model file in this repo uses legacy `Column(...)` style (`id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)` etc.). Mixing the two styles in the same model is legal but harms readability and consistency, and the plan's `<behavior>` section explicitly says "Place this column declaration near the other String column declarations (matching existing alphabetical or logical grouping — read each file first)."
- **Fix:** Adopted the existing legacy `Column(String(20), nullable=False, server_default="seva")` style on all 6 model files. This preserves intra-file consistency. The `Mapped[]` migration is a separate, repo-wide concern not in scope for Phase 9.
- **Files modified:** All 6 model files (same files as Deviation 3)
- **Commit:** 6e11fa2

## Wave 0 Backend RED → GREEN Test Count Delta

Before Wave 1 (post-09-01):
- backend: 156 pass + 6 skipped (Wave 0 RED, including the 4 in test_migration_0014, the 4 in test_queries_scoped, the 1 in test_daily_summary_parity, and 1+ in test_multitenant_isolation.py)

After Wave 1 (this plan):
- backend: 165 pass + 6 skipped (the remaining 6 are test_multitenant_isolation.py — TENANT-10 scaffolds reserved for Wave 2 router refactor; not in this plan's scope)

Net delta: +9 tests flipped from skipped to green (4 test_migration_0014, 4 test_queries_scoped, 1 test_daily_summary_parity).

## CI Grep Gate Status

`bash scripts/verify-tenant-isolation.sh` → EXIT 0.

The 5 pre-existing call sites in `PRE_WAVE_2_WHITELIST` (3 backend routers + 2 scheduler agents) remain on the temporary whitelist. Wave 2 will refactor each call site to use the new `scoped_*()` helpers and delete each whitelist entry in the same commit that replaces the call site.

## Database State Post-Migration

- `alembic_version.version_num` = `0014`
- All 3 multi-tenant tables verified via `information_schema`:
  - `company_id`: `character varying(20)`, `is_nullable='NO'`, `column_default="'seva'::character varying"`
- All 3 `ck_<table>_company_id` CHECK constraints verified via `pg_catalog.pg_constraint`:
  - Definition: `CHECK (((company_id)::text = ANY ((ARRAY['seva'::character varying, 'juno'::character varying])::text[])))`
- All 3 composite indexes verified via `pg_catalog.pg_indexes` (each contains `company_id` as the leading column).
- `SELECT DISTINCT company_id FROM daily_summaries` returns `['seva']` — 12 existing rows backfilled atomically by `server_default`.
- `INSERT ... company_id='bogus'` confirmed to raise `IntegrityError` via the CHECK.

## Handoff to Wave 2 (09-03-PLAN.md)

Wave 2 owns the router + scheduler refactor:

1. Refactor `backend/app/routers/{summaries,calendar,weekly_sweeps}.py` to depend on `get_current_company` (from `app.dependencies`) and `scoped_summaries`/`scoped_calendar`/`scoped_weekly_sweeps` (from `app.queries`). Delete each router's entry from `scripts/verify-tenant-isolation.sh`'s `PRE_WAVE_2_WHITELIST` in the same commit.
2. Add `/api/{company}` prefix to each tenant-scoped router in `backend/app/main.py`.
3. Refactor `scheduler/agents/daily_summary.py` and `scheduler/agents/weekly_sweeper.py` to accept `company_id` (factory closure pattern per CONTEXT.md D-01). Delete the scheduler entries from `PRE_WAVE_2_WHITELIST` in the same commit.
4. Add `juno_daily_summary=1020` + `juno_weekly_sweeper=1021` to `JOB_LOCK_IDS` in `scheduler/worker.py`; register the `juno_daily_summary` cron with `CronTrigger(hour="8,12", minute=5, timezone="America/Los_Angeles")` (5-min stagger per CONTEXT.md D-01a).
5. Optional minimal `scheduler/companies/juno/` skeleton (per CONTEXT.md "Claude's discretion") writing `status='partial'` rows until Phase 10 fills real content.

## Known Stubs

None. Wave 1 ships only production-grade code; the scoped helpers are exercised by 4 compile-SQL tests and the migration is applied + round-trip-verified on Neon. The `get_current_company` dep is callable but not yet wired into any router (intentional — Wave 2's scope).

## Self-Check: PASSED

All 16 file paths verified to exist on disk. All 3 task commits (b836714, 6e11fa2, 3cae047) verified to exist in `git log`. Final-metadata commit will be the 4th commit, captured separately.
