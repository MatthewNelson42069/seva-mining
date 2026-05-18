---
phase: 05-foundation-tabs-db-backend-stubs
plan: 02
subsystem: database
tags: [alembic, postgres, sqlalchemy, migration, calendar, weekly-sweeps, neon]

requires:
  - phase: 01-foundation
    provides: agent_runs table (FK target for weekly_sweeps.agent_run_id)
  - phase: 04-daily-summaries-v2
    provides: 0010 alembic head, daily_summaries table (template pattern for 0011/0012)
provides:
  - calendar_items table (DB-01) — Phase 6 Content Calendar surface
  - weekly_sweeps table (DB-02) — Phase 7 Weekly Viral Sweeper persistence
  - alembic head advanced 0010 → 0012 (single linear chain, no branches)
affects:
  - 06-content-calendar (consumes calendar_items via CRUD endpoints)
  - 07-weekly-viral-sweeper (writes weekly_sweeps rows from Sunday cron)
  - backend models layer (next plan 05-03 will add SQLAlchemy ORM models)

tech-stack:
  added: []
  patterns:
    - Hand-written Alembic migration (NO --autogenerate, mirrors 0010 template)
    - sa.Date() for day-only columns to prevent UTC off-by-one (P2 critical pitfall)
    - ondelete="SET NULL" on agent_run_id FK (preserves content on agent_runs cleanup)
    - Descending index expression via sa.text("generated_at DESC") for ORDER BY DESC queries

key-files:
  created:
    - backend/alembic/versions/0011_add_calendar_items.py
    - backend/alembic/versions/0012_add_weekly_sweeps.py
  modified: []

key-decisions:
  - "sa.Date() (not sa.DateTime) for calendar_items.date, weekly_sweeps.week_start, week_end — eliminates UTC off-by-one risk on Railway"
  - "Migration chain verified pre-write (alembic heads = 0010) and post-write via end-to-end round-trip"
  - "Descending index on weekly_sweeps.generated_at via sa.text(\"generated_at DESC\") — matches Phase 7 ORDER BY DESC query pattern"
  - "tag CHECK constraint with 6 enum values applied separately via op.create_check_constraint (template parity with 0010)"

patterns-established:
  - "Pre-write alembic heads check: verify expected head BEFORE writing new migration file (catches stale branches early)"
  - "Round-trip verification: upgrade head → downgrade -1 → downgrade -1 → upgrade head proves both up and down paths cleanly"

requirements-completed: [DB-01, DB-02, DB-05]

duration: 7min
completed: 2026-05-18
---

# Phase 05 Plan 02: Alembic Migrations for calendar_items + weekly_sweeps Summary

**Two hand-written Alembic migrations (0011 + 0012) creating calendar_items (Phase 6 surface) and weekly_sweeps (Phase 7 surface) tables, advancing the migration chain from 0010 to 0012 with verified round-trip.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-18T21:29Z (approx)
- **Completed:** 2026-05-18T21:36:41Z
- **Tasks:** 2
- **Files modified:** 2 (both newly created)

## Accomplishments

- **DB-01 shipped:** `calendar_items` table created in Postgres (Neon dev DB) with `date DATE NOT NULL`, `title TEXT NOT NULL`, `notes_md TEXT NULL`, `tag` enum CHECK (thread/video/podcast/tweet/idea/other), `ix_calendar_items_date` index, UUID PK with `gen_random_uuid()` default, `created_at`/`updated_at` timestamptz with `now()` defaults.
- **DB-02 shipped:** `weekly_sweeps` table created with `generated_at` timestamptz, `week_start`/`week_end` DATE columns, three markdown TEXT body columns, `raw_sources_jsonb` JSONB, status CHECK (completed/failed/partial), `agent_run_id` FK with `ondelete=SET NULL`, and `ix_weekly_sweeps_generated_at` DESC index.
- **DB-05 shipped:** alembic chain integrity verified end-to-end. Pre-write `alembic heads` = `0010 (head)`. Post-write round-trip: upgrade head (0010→0011→0012) → downgrade -1 (0012→0011) → downgrade -1 (0011→0010) → upgrade head (0010→0011→0012). Final dev DB state: `0012 (head)`.

## Task Commits

Each task was committed atomically (with `--no-verify` per Wave 1 parallel executor protocol):

1. **Task 1: Verify alembic head and create 0011_add_calendar_items migration** — `7e2b84a` (feat)
2. **Task 2: Create 0012_add_weekly_sweeps migration and verify round-trip** — `e5b09cd` (feat)

**Plan metadata commit:** (next, after STATE/ROADMAP updates)

## Files Created/Modified

- `backend/alembic/versions/0011_add_calendar_items.py` (69 lines) — Hand-written migration creating `calendar_items` table. Module-level `revision = "0011"`, `down_revision = "0010"`. Uses `sa.Date()` for the `date` column per P2 critical pitfall (UTC off-by-one prevention). Tag CHECK constraint with 6 enum values added via separate `op.create_check_constraint` call (template parity with 0010). `ix_calendar_items_date` index for Phase 6 weekly-grid queries that filter by date range.
- `backend/alembic/versions/0012_add_weekly_sweeps.py` (78 lines) — Hand-written migration creating `weekly_sweeps` table. Module-level `revision = "0012"`, `down_revision = "0011"` (chains off 0011, NOT 0010 — P1 critical pitfall prevented). `week_start` and `week_end` use `sa.Date()` (same TZ rationale). `agent_run_id` FK uses `ondelete="SET NULL"` (mirrors `daily_summaries` pattern — manual cleanup of `agent_runs` preserves sweep content). `raw_sources_jsonb` is `postgresql.JSONB(astext_type=sa.Text())` for storing Reddit + virality input snapshots. `ix_weekly_sweeps_generated_at` is a descending index via `sa.text("generated_at DESC")` to match Phase 7 `ORDER BY generated_at DESC` queries.

## Pre-Write `alembic heads` Output (DB-05 proof)

```
$ cd backend && uv run alembic heads
0010 (head)
```

Single head confirmed before writing 0011. No branches, no stale revisions.

## Round-Trip Command Transcript (DB-05 verification)

```
=== Step 1: alembic upgrade head ===
INFO  [alembic.runtime.migration] Running upgrade 0010 -> 0011, Add calendar_items table — v2.1 Phase 5 (DB-01).
INFO  [alembic.runtime.migration] Running upgrade 0011 -> 0012, Add weekly_sweeps table — v2.1 Phase 5 (DB-02).

=== Step 2: alembic current ===
0012 (head)

=== Step 3: downgrade -1 (rollback 0012) ===
INFO  [alembic.runtime.migration] Running downgrade 0012 -> 0011, Add weekly_sweeps table — v2.1 Phase 5 (DB-02).

=== Step 4: alembic current (expect 0011) ===
0011

=== Step 5: downgrade -1 (rollback 0011) ===
INFO  [alembic.runtime.migration] Running downgrade 0011 -> 0010, Add calendar_items table — v2.1 Phase 5 (DB-01).

=== Step 6: alembic current (expect 0010) ===
0010

=== Step 7: alembic upgrade head (re-apply) ===
INFO  [alembic.runtime.migration] Running upgrade 0010 -> 0011, Add calendar_items table — v2.1 Phase 5 (DB-01).
INFO  [alembic.runtime.migration] Running upgrade 0011 -> 0012, Add weekly_sweeps table — v2.1 Phase 5 (DB-02).

=== Step 8: alembic current (expect 0012) ===
0012 (head)

=== Final: alembic heads ===
0012 (head)
```

History chain (top 3):

```
0011 -> 0012 (head), Add weekly_sweeps table — v2.1 Phase 5 (DB-02).
0010 -> 0011, Add calendar_items table — v2.1 Phase 5 (DB-01).
0009 -> 0010, Add daily_summaries table for v2.0 daily summary feed.
```

## Why `sa.Date()` for Day-Only Columns (P2 Pitfall Prevention)

Three columns store calendar days (not instants): `calendar_items.date`, `weekly_sweeps.week_start`, `weekly_sweeps.week_end`. All use `sa.Date()` which maps to Postgres `DATE` (no time, no timezone).

**The pitfall avoided:** if any of these were `sa.DateTime()` (instant), then a PT user creating a calendar item on May 17 at 22:30 PT would be stored as `2026-05-18 05:30:00 UTC` on the Railway server. When the frontend queried "items on 2026-05-17", the row would be missed because UTC normalization shifted the timestamp into the next day. Using `DATE` stores the literal calendar day with no timezone semantics — `2026-05-17` is `2026-05-17` regardless of server or client TZ.

`created_at` and `updated_at` use `sa.DateTime(timezone=True)` because they ARE instants (the moment a row was written), and Postgres stores those as `timestamptz` (UTC normalized) — that's the correct type for instants.

## Decisions Made

- **Followed plan exactly as written** for migration file contents — both files match the prescribed source character-for-character.
- **Loaded DATABASE_URL from `backend/.env` via `set -a && source .env && set +a`** for the round-trip alembic commands — the env file already exists with the Neon pooler DSN.
- **Skipped `alembic check` step** at start of Task 2 — when the dev DB is at 0010 but the model metadata reflects the future state (post-0012), `alembic check` reports "Target database is not up to date" which is not the kind of inconsistency `check` is meant to catch. The end-to-end round-trip in Step 3 is the authoritative validation of chain consistency and proved both migrations apply cleanly in both directions.

## Deviations from Plan

**1. [Plan inconsistency — kept prescribed content] Task 1 verify spec mismatch on `sa.DateTime` count**

- **Found during:** Task 1 verification step
- **Issue:** The plan's automated verify expects `grep -c "sa.DateTime" 0011_add_calendar_items.py` = `2` (for the two `created_at`/`updated_at` columns), but the plan's own prescribed file content includes a docstring sentence "...NOT `sa.DateTime()`. Postgres stores..." — that third occurrence makes the actual grep count `3`.
- **Resolution:** Kept the prescribed docstring (the plan's source-of-truth file content is the contract). The intent — `date` column uses `sa.Date()`, not `sa.DateTime` — is independently verified by `grep -c 'sa.Column("date", sa.Date()'` returning `1` (passed). No code-level pitfall introduced.
- **Files affected:** none (no code change required)
- **Verification:** `grep -c 'sa.Column("date", sa.Date()` = 1; round-trip succeeded.

**2. [Plan procedural step skipped] `alembic check` (Task 2 Step 2)**

- **Found during:** Task 2 Step 2 attempt
- **Issue:** `alembic check` failed with "Target database is not up to date" because the dev DB was at 0010 while the new model metadata (once Plan 03 lands) would reflect the post-0012 state. `alembic check` is designed to detect schema drift between model definitions and DB head; running it before the model files exist (Plan 03) and before upgrading is a no-op at best.
- **Resolution:** Proceeded directly to the round-trip (Step 3), which is the authoritative chain-integrity test. Both upgrades and both downgrades succeeded cleanly.
- **Files affected:** none
- **Verification:** Round-trip transcript above shows the chain is consistent.

---

**Total deviations:** 0 functional changes; 2 documentation-level notes (one plan verify-spec inconsistency, one procedural step skipped for cause).
**Impact on plan:** Zero impact on output. Both migration files match the plan's prescribed content exactly. Final DB state matches expected (`0012 (head)`). DB-01, DB-02, DB-05 all satisfied.

## Issues Encountered

- **`uv run alembic` requires DATABASE_URL in environment** — the alembic `env.py` reads `os.environ.get("DATABASE_URL")` directly; running alembic commands without sourcing `.env` first produces `NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:driver`. Resolved by `set -a && source backend/.env && set +a` before each alembic invocation in the round-trip script.

## User Setup Required

None — all migrations applied to existing Neon dev DB using already-configured `DATABASE_URL`. No new env vars introduced.

## Next Phase Readiness

- **Plan 05-03 (SQLAlchemy ORM models)** can now reference `calendar_items` and `weekly_sweeps` tables — the schema is live on dev DB.
- **Plan 05-04 / 05-05 (FastAPI route stubs)** can target the new tables.
- **Phase 6 (Content Calendar)** can begin CRUD work against `calendar_items` once Plan 05-03 lands the ORM model.
- **Phase 7 (Weekly Viral Sweeper)** can begin writing weekly sweep rows once ORM model + REST endpoint land.
- No blockers.

## Self-Check: PASSED

- `backend/alembic/versions/0011_add_calendar_items.py` — FOUND
- `backend/alembic/versions/0012_add_weekly_sweeps.py` — FOUND
- Commit `7e2b84a` (Task 1) — FOUND in git log
- Commit `e5b09cd` (Task 2) — FOUND in git log
- Dev DB at `0012 (head)` — verified via `alembic current`

---

*Phase: 05-foundation-tabs-db-backend-stubs*
*Completed: 2026-05-18*
