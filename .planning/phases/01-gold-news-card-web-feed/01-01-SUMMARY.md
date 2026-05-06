---
phase: 01-gold-news-card-web-feed
plan: "01"
subsystem: database
tags: [sqlalchemy, alembic, pydantic, postgresql, jsonb, migration]

# Dependency graph
requires: []
provides:
  - "Alembic migration 0010 creating daily_summaries table (11 columns, CHECK constraint, index)"
  - "backend/app/models/daily_summary.py: DailySummary SQLAlchemy model"
  - "scheduler/models/daily_summary.py: DailySummary SQLAlchemy model (byte-for-byte parity)"
  - "backend/app/schemas/daily_summary.py: RawSources, GoldNewsSource, OntarioLawState, OntarioStatsState, SummaryCardResponse, SummaryFeedResponse"
  - "scheduler/tests/test_daily_summary_model.py: 12 parity tests"
  - "backend/tests/test_daily_summary_schema.py: 7 schema validation tests"
affects:
  - 01-02-summaries-router
  - 01-03-daily-summary-agent
  - 01-04-scheduler-worker-integration
  - 01-05-frontend-feed-page

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dual-model parity: backend and scheduler share identical SQLAlchemy models differing only in Base import path"
    - "Hand-written Alembic migration (op.create_table + op.create_check_constraint + op.create_index only — no autogenerate)"
    - "RawSources Pydantic model gates JSONB writes (HIGH-4 schema-drift mitigation)"
    - "Parity test enforces column lockstep via 12 hasattr assertions (mirrors test_draft_item_model.py)"

key-files:
  created:
    - backend/alembic/versions/0010_add_daily_summaries.py
    - backend/app/models/daily_summary.py
    - scheduler/models/daily_summary.py
    - scheduler/tests/test_daily_summary_model.py
    - backend/app/schemas/daily_summary.py
    - backend/tests/test_daily_summary_schema.py
  modified:
    - backend/app/models/__init__.py
    - scheduler/models/__init__.py

key-decisions:
  - "Migration is hand-written (op.create_table only) — autogenerate risks spurious DDL against the ApprovalState enum from migration 0009 (MOD-2)"
  - "DailySummary models in backend and scheduler are byte-for-byte identical except Base import path — enforced by parity test"
  - "SummaryCardResponse omits raw_sources_jsonb to avoid sending large forensics blob to the feed endpoint"
  - "RawSources Pydantic model locks the JSONB shape at application level (no DB-level enforcement) — HIGH-4 closed"

requirements-completed:
  - SUM-05

# Metrics
duration: 4min
completed: "2026-05-06"
---

# Phase 1 Plan 01: DB Foundation (Migration, Models, Schemas) Summary

**Alembic migration 0010 creating daily_summaries table, dual SQLAlchemy parity models (backend + scheduler), and Pydantic schemas with strict RawSources JSONB validator (HIGH-4 closed)**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-06T16:10:56Z
- **Completed:** 2026-05-06T16:14:55Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Hand-written Alembic migration 0010 chains from 0009, creates daily_summaries with 11 columns + CHECK constraint (status IN completed/failed/partial) + index on generated_at + FK to agent_runs ON DELETE SET NULL
- Dual DailySummary SQLAlchemy models (backend and scheduler) are byte-for-byte identical, parity enforced by 12 hasattr tests in test_daily_summary_model.py
- RawSources Pydantic model with strict field types and score bounds (ge=0.0, le=10.0) closes HIGH-4 schema-drift pitfall; SummaryCardResponse intentionally omits raw_sources_jsonb

## Task Commits

Each task was committed atomically:

1. **Task 1: Migration 0010** - `0c0ff79` (feat)
2. **Task 2: Dual SQLAlchemy DailySummary models** - `9d7855d` (feat)
3. **Task 3: Pydantic schemas** - `86fff8a` (feat)
4. **Ruff fix** - `5e4f16e` (fix — import organization in daily_summary schema)

## Files Created/Modified

- `backend/alembic/versions/0010_add_daily_summaries.py` - Hand-written migration creating daily_summaries table (chains from 0009)
- `backend/app/models/daily_summary.py` - DailySummary SQLAlchemy model (backend); 11 columns
- `scheduler/models/daily_summary.py` - DailySummary SQLAlchemy model (scheduler parity); byte-for-byte identical except Base import
- `scheduler/tests/test_daily_summary_model.py` - 12 parity tests (tablename + 11 column hasattr assertions)
- `backend/app/schemas/daily_summary.py` - GoldNewsSource, OntarioLawHit, OntarioLawState, OntarioStatsState, RawSources, SummaryCardResponse, SummaryFeedResponse
- `backend/tests/test_daily_summary_schema.py` - 7 schema validation tests (construction, score bounds, wrong type, round-trip, omit check)
- `backend/app/models/__init__.py` - Added DailySummary import + __all__ entry
- `scheduler/models/__init__.py` - Added DailySummary import + __all__ entry

## daily_summaries Column List

id (UUID PK), generated_at (TIMESTAMPTZ NOT NULL), period_label (VARCHAR(20) NOT NULL), gold_news_md (TEXT nullable), ontario_law_md (TEXT nullable), ontario_stats_md (TEXT nullable), raw_sources_jsonb (JSONB nullable), status (VARCHAR(20) NOT NULL DEFAULT 'completed'), error_text (TEXT nullable), agent_run_id (UUID FK->agent_runs.id ON DELETE SET NULL), created_at (TIMESTAMPTZ NOT NULL DEFAULT now())

## RawSources Schema Shape

```
RawSources:
  gold_news: list[GoldNewsSource]        # {title, link, source_name, score (0-10), published_at}
  ontario_law: OntarioLawState           # {hits: list[OntarioLawHit], last_known_law: OntarioLawHit | None}
  ontario_stats: OntarioStatsState       # {snapshot_date: str, last_known_figure: float | None, fresh_data: dict | None}
```

Phase 1 ships with ontario_law and ontario_stats as empty stubs; Phase 2/3 populate them.

## Decisions Made

- Hand-written migration only (no autogenerate) — autogenerate risks spurious DDL against the ApprovalState PG enum from migration 0009 (MOD-2 pitfall)
- Dual-model parity enforced by test (mirror of test_draft_item_model.py pattern established in Phase B)
- SummaryCardResponse intentionally omits raw_sources_jsonb (large forensics blob — detail endpoint can expose it later)
- RawSources field types are strict (list, not Any) so malformed writes fail at application layer before reaching Postgres

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff import organization error in daily_summary schema**
- **Found during:** Post-task ruff check on backend
- **Issue:** Missing blank line between docstring and import block; ruff E302 import organization error
- **Fix:** Ran `ruff check --fix` to auto-sort import block; no logic change
- **Files modified:** backend/app/schemas/daily_summary.py
- **Verification:** `uv run ruff check .` exits 0; all 7 schema tests still pass
- **Committed in:** `5e4f16e` (separate fix commit)

---

**Total deviations:** 1 auto-fixed (import organization — no scope creep)
**Impact on plan:** Trivial formatting fix; no functional or behavioral change.

## Issues Encountered

None — all three tasks executed cleanly against the plan specification.

## User Setup Required

None — migration 0010 must be run manually via `alembic upgrade head` against the Neon Postgres DB (standard deploy step). The migration file is committed and ready.

## Known Stubs

- `OntarioLawState` and `OntarioStatsState` default to empty (hits=[], last_known_law=None, snapshot_date="", etc.) — intentional Phase 1 stubs. Phase 2 (Ontario law ingestion) and Phase 3 (Ontario stats) will populate these.
- This does NOT prevent the plan's goal: the table, models, and schema contracts are fully functional for the Gold News section (Phase 1 scope).

## Next Phase Readiness

- Plan 01-02 (summaries router) can import DailySummary ORM + SummaryCardResponse/SummaryFeedResponse schemas immediately
- Plan 01-03 (daily_summary agent) can import DailySummary ORM + RawSources schema immediately
- Migration 0010 must be applied to Neon before Plan 01-02 or 01-03 integration tests run against a live DB
- All 204 scheduler tests and 99 backend tests pass (no regressions)

---
*Phase: 01-gold-news-card-web-feed*
*Completed: 2026-05-06*
