---
phase: 07-weekly-viral-sweeper
plan: 01
subsystem: api
tags: [pydantic-v2, schemas, requirements, x-api, weekly-sweeper]

# Dependency graph
requires:
  - phase: 05-foundation-tabs-db-backend-stubs
    provides: weekly_sweeps table (Alembic 0012), WeeklySweep ORM model with reddit_top_md/story_virality_md/content_angles_md columns, stub /weekly-sweeps router
provides:
  - WeeklySweepCard Pydantic v2 schema mirroring weekly_sweeps columns (raw_sources_jsonb omitted)
  - WeeklySweepFeedResponse list wrapper for GET /weekly-sweeps
  - REQUIREMENTS.md rescoped for X-API pivot (SWEEP-01/02 Dropped; SWEEP-04/05 replaced; SWEEP-08/13 rephrased)
  - Frozen API contract for downstream Plans 07-03 (read route), 07-06 (frontend)
affects: [07-02, 07-03, 07-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Pydantic v2 ConfigDict(from_attributes=True) ORM-attribute serialization (mirrors SummaryCardResponse)
    - Literal["completed","failed","partial"] status field matches Phase 5 migration 0012 CHECK constraint
    - {Card, FeedResponse} pair shape for paginated feed endpoints

key-files:
  created:
    - backend/app/schemas/weekly_sweep.py
  modified:
    - .planning/REQUIREMENTS.md

key-decisions:
  - "Preserved column name reddit_top_md from Phase 5 migration even though Phase 7 stores X posts in it — renaming would require a migration with zero functional benefit (per 07-CONTEXT.md X-API pivot)"
  - "Marked SWEEP-01 and SWEEP-02 as Dropped (not deleted) with strikethrough markdown and traceability table updates — preserves historical context and ID continuity for the verifier"
  - "Used surgical Edit operations rather than file rewrite to keep git diff minimal (9 lines changed, all SWEEP-related)"

patterns-established:
  - "Pattern: Dropped requirements use [x] checkbox + (DROPPED — reason) prefix + ~~strikethrough~~ on original text + replacement rationale — preserves traceability"
  - "Pattern: Pydantic v2 schemas live in backend/app/schemas/{table_name}.py, export {Table}Card + {Table}FeedResponse pair matching the existing daily_summary.py shape"

requirements-completed: [SWEEP-01, SWEEP-02, SWEEP-04, SWEEP-05, SWEEP-08, SWEEP-12, SWEEP-13]

# Metrics
duration: ~3 min
completed: 2026-05-19
---

# Phase 7 Plan 01: Schema + Requirements Foundation Summary

**Pydantic v2 WeeklySweepCard + WeeklySweepFeedResponse schemas added (mirroring SummaryCardResponse shape) and REQUIREMENTS.md surgically rescoped to reflect the X-API pivot — Reddit ingestion language replaced with tweepy.AsyncClient recent-search semantics across SWEEP-04/05/08/13; SWEEP-01/02 marked Dropped in both the requirements list and traceability table.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-19T05:02:21Z
- **Completed:** 2026-05-19T05:04:46Z
- **Tasks:** 2
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments
- Backend has a frozen Pydantic v2 contract for the weekly sweep card (WeeklySweepCard) and feed list wrapper (WeeklySweepFeedResponse), both importable from `app.schemas.weekly_sweep`
- REQUIREMENTS.md reflects the X-API pivot accurately — no live `asyncpraw`, `fetch_reddit_posts`, or subreddit-list mentions remain outside of strikethrough markdown
- Traceability table updated: SWEEP-01 + SWEEP-02 marked `Dropped (X-API pivot)`, all other SWEEP-* (03/06/07/09/10/11/12/14) intentionally untouched and still `Pending` for downstream plans
- The 07-01 contract foundation is locked, so 07-02 (scheduler) / 07-03 (read route) / 07-06 (frontend) can develop against frozen interfaces

## Task Commits

Each task was committed atomically via gsd-tools:

1. **Task 1: Surgically rescope SWEEP-* requirements for X-API pivot** - `92f7c6b` (docs)
2. **Task 2: Create Pydantic v2 schemas for weekly sweep card + feed response** - `51d1b8b` (feat)

## Files Created/Modified

- **Created:** `backend/app/schemas/weekly_sweep.py` — 45 lines; exports `WeeklySweepCard` (12 fields: id, generated_at, week_start, week_end, reddit_top_md, story_virality_md, content_angles_md, status [Literal], error_text, agent_run_id) + `WeeklySweepFeedResponse` (sweeps: list[WeeklySweepCard], total: int). Uses `model_config = ConfigDict(from_attributes=True)` for ORM serialization; mirrors `daily_summary.py` pattern exactly.
- **Modified:** `.planning/REQUIREMENTS.md` — 9 lines changed:
  - SWEEP section description: live `asyncpraw` mention rewritten to `tweepy.asynchronous.AsyncClient` with `~~asyncpraw~~` strikethrough reference
  - SWEEP-01: `[x] DROPPED — X-API pivot per 07-CONTEXT.md D-03` with strikethrough original text
  - SWEEP-02: `[x] DROPPED — X-API pivot per 07-CONTEXT.md D-03` with strikethrough original text
  - SWEEP-04: replaced `reddit_ingest.py / fetch_reddit_posts / asyncpraw.Reddit` with `x_ingest.py / fetch_top_x_posts / tweepy.AsyncClient.search_recent_tweets`, includes quota gate spec
  - SWEEP-05: replaced 4-subreddit list with combined keyword+cashtag+hashtag X recent-search query (`max_results=100`, engagement re-rank `likes + retweets*2 + replies*1.5`)
  - SWEEP-08: rephrased "Reddit signal" → "X signal", `len(reddit_posts) < 3` → `len(x_posts) < 3`, added 500-char truncation note
  - SWEEP-13: rephrased "Top Reddit Posts This Week" → "Top X Posts This Week", added stacked-sections clarification and `max-w-[720px]` width reference
  - Traceability table: SWEEP-01/02 rows changed `Pending` → `Dropped (X-API pivot)`

## Decisions Made

- **Preserved `reddit_top_md` column name** in WeeklySweepCard (with explanatory comment) — Phase 5 migration 0012 created this column for Reddit content; Phase 7 stores X posts in the same column rather than triggering a no-functional-benefit migration. Frontend will display it as "Top X Posts This Week" regardless.
- **Surgical Edit operations over file rewrite** for REQUIREMENTS.md — git diff is 9 lines, all SWEEP-related; TAB-*, DB-*, CAL-*, UI-* sections untouched per plan instructions.
- **Followed `daily_summary.py` pattern exactly** for the Pydantic schemas — no novel patterns introduced.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated the SWEEP section header narrative to scrub live `asyncpraw` mention**
- **Found during:** Task 1 verification step
- **Issue:** Plan's overall verification check #3 requires `grep "asyncpraw" .planning/REQUIREMENTS.md | grep -v "~~" | wc -l` to return 0. The plan's explicit action items only covered SWEEP-01/02/04/05/08/13 entries, but line 47 (the narrative description of the SWEEP section) also contained a live "Reddit ingestion via asyncpraw" mention that would have failed the verification gate.
- **Fix:** Rewrote line 47 to describe X-post ingestion via `tweepy.asynchronous.AsyncClient` recent search, with `~~asyncpraw~~` strikethrough reference noting the originally specced source. Scope: 1 line, SWEEP-section only.
- **Files modified:** `.planning/REQUIREMENTS.md`
- **Verification:** `grep "asyncpraw" .planning/REQUIREMENTS.md | grep -v "~~" | wc -l` returns 0; live asyncpraw mentions eliminated.
- **Committed in:** `92f7c6b` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 Rule 3 - blocking)
**Impact on plan:** Single-line surgical narrative scrub required to satisfy the plan's own overall verification gate. No scope creep — change is strictly within the SWEEP section the plan was already editing.

## Issues Encountered

- **`SWEEP-` count discrepancy with plan's overall verification text:** Plan's overall verification check #2 stated `grep -c "SWEEP-" .planning/REQUIREMENTS.md` should return 28 (14 IDs × 2 occurrences). Actual count is 33 because the file pre-existed with 5 additional `SWEEP-{NAME}-v22` entries in the v2.2 Sweeper Enhancements deferred section (lines 87-91: SWEEP-WHATSAPP-v22, SWEEP-WSB-v22, SWEEP-FRED-v22, SWEEP-KITCO-v22, SWEEP-X-v22). 14 main + 5 v2.2 deferred + 14 traceability = 33. Pre-edit count was also 33 → Task 1's acceptance criterion ("same count as before edit") is satisfied. The plan's check #2 was a planner-side miscount that didn't account for the v2.2 entries; the actual intent (no SWEEP IDs lost or duplicated) is met. No action needed.

## User Setup Required

None — no external service configuration required for this plan. The X API env vars (`x_api_bearer_token`) are already wired in Railway from the Content Agent's `video_clip` pipeline (per 07-CONTEXT.md D-03 and CLAUDE.md historical note 2026-04-20).

## Next Phase Readiness

- **Frozen API contract:** Plans 07-02 / 07-03 / 07-06 can develop against `WeeklySweepCard` and `WeeklySweepFeedResponse` without further schema work.
- **Requirements alignment:** REQUIREMENTS.md SWEEP entries now match 07-CONTEXT.md decisions D-03 through D-08 verbatim — verifier will not flag a Reddit/X mismatch.
- **No blockers** for the rest of Phase 7 waves.

## Self-Check: PASSED

Verified post-write:
- `backend/app/schemas/weekly_sweep.py` exists and imports cleanly (`uv run python -c "from app.schemas.weekly_sweep import WeeklySweepCard, WeeklySweepFeedResponse"` exits 0)
- `WeeklySweepCard.model_config.get('from_attributes') is True` — assertion passes
- Both fields `sweeps` and `total` present in `WeeklySweepFeedResponse.model_fields`
- All 8 grep-based Task 1 acceptance criteria pass (SWEEP-01/02 DROPPED, x_ingest.py, fetch_top_x_posts, sort_order="relevancy", Top X Posts This Week, len(x_posts) < 3, no fetch_reddit_posts, no Wallstreetsilver)
- All 7 grep-based Task 2 acceptance criteria pass (file exists, both classes defined, ConfigDict from_attributes, Literal status, no Pydantic v1 Config class, key_links pattern match)
- Commits `92f7c6b` and `51d1b8b` present in `git log`

---
*Phase: 07-weekly-viral-sweeper*
*Completed: 2026-05-19*
