---
phase: 07-content-agent
plan: 05
subsystem: scheduler
tags: [content-agent, feedparser, serpapi, claude-haiku, claude-sonnet, asyncio, apscheduler, python]

# Dependency graph
requires:
  - phase: 07-03
    provides: extract_article_text, fetch_article, _search_corroborating, _research_and_draft
  - phase: 07-04
    provides: check_compliance, build_no_story_bundle, build_draft_item

provides:
  - scheduler/agents/content_agent.py — complete pipeline: _run_pipeline, _fetch_all_rss, _fetch_all_serpapi, _score_relevance, _get_config, run()
  - scheduler/worker.py — ContentAgent wired to content_agent job (replaces placeholder)
  - Full ingest-dedup-score-research-draft-comply-persist orchestration flow
  - RSS_FEEDS (4 feeds) and SERPAPI_KEYWORDS (6 keywords) module-level constants

affects:
  - Phase 08 (dashboard integration uses ContentBundle and DraftItem from this pipeline)
  - Senior Agent receives DraftItems via process_new_items() from this pipeline

# Tech tracking
tech-stack:
  added:
    - feedparser (called in run_in_executor for non-blocking RSS fetch)
  patterns:
    - asyncio.gather + run_in_executor for concurrent RSS + SerpAPI ingestion
    - AgentRun records items_found, items_queued, items_filtered, status, notes, errors
    - Lazy import pattern: 'from models.content_bundle import ContentBundle' inside pipeline to avoid circular deps
    - Lazy import pattern: 'from agents.senior_agent import process_new_items' inside pipeline to avoid circular deps
    - _extract_check_text module-level helper extracts all text from any draft format for compliance

key-files:
  created: []
  modified:
    - scheduler/agents/content_agent.py
    - scheduler/worker.py
    - scheduler/tests/test_content_agent.py

key-decisions:
  - "RSS_FEEDS and SERPAPI_KEYWORDS are module-level constants — accessible as ca.RSS_FEEDS and ca.SERPAPI_KEYWORDS in tests without class instantiation"
  - "run() creates and commits AgentRun immediately before pipeline starts — status visible even if pipeline crashes mid-flight"
  - "ContentBundle imported lazily inside _run_pipeline to avoid circular import with models"
  - "process_new_items imported lazily inside _run_pipeline to avoid circular import with senior_agent"
  - "_extract_check_text is module-level (not class method) — consistent with established pattern for testable pure functions"

patterns-established:
  - "Concurrent multi-source ingestion: asyncio.gather wrapping run_in_executor for sync libraries (feedparser, serpapi)"
  - "AgentRun lifecycle: commit immediately on creation (status=running), update in try/finally (status=completed|failed)"

requirements-completed: [CONT-01, CONT-02, CONT-03]

# Metrics
duration: 5min
completed: 2026-04-02
---

# Phase 7 Plan 05: Full Pipeline Assembly Summary

**Complete Content Agent pipeline wired end-to-end: RSS + SerpAPI concurrent ingestion via asyncio.gather/run_in_executor, Claude Haiku relevance scoring, dedup+selection, deep research, Sonnet drafting, compliance, DraftItem creation, and ContentAgent wired to worker.py — 16/16 tests pass**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-02T23:34:40Z
- **Completed:** 2026-04-02T23:39:00Z
- **Tasks:** 2 (+ Task 3 human-verify checkpoint pending)
- **Files modified:** 3

## Accomplishments

- Implemented `_run_pipeline()` — orchestrates the full 10-step ingest-dedup-score-research-draft-comply-persist flow with complete AgentRun logging
- Implemented `_fetch_all_rss()` — fetches all 4 RSS feeds concurrently via asyncio.gather + run_in_executor(feedparser.parse)
- Implemented `_fetch_all_serpapi()` — runs 6 SerpAPI keyword searches concurrently via asyncio.gather + run_in_executor
- Implemented `_score_relevance()` — Claude Haiku call for gold-sector relevance scoring (0-1 scale, neutral default 0.5 on failure)
- Implemented `_get_config()` — reads config keys from DB at runtime (same pattern as instagram_agent.py)
- Implemented `run()` — creates AgentRun, calls _run_pipeline, updates status to completed/failed in finally block
- Added `_extract_check_text()` module-level helper for compliance text extraction across all 3 format types
- Added `RSS_FEEDS` and `SERPAPI_KEYWORDS` module-level constants
- Wired ContentAgent to `worker.py` — replaces placeholder else-branch with proper `elif job_name == "content_agent"` with advisory lock
- All 16 tests pass (previously 15 with 1 skipped — the scheduler_wiring test is now fully active)

## Task Commits

1. **Task 1: Implement _run_pipeline and RSS/SerpAPI ingest methods** — `87a678a` (feat)
2. **Task 2: Wire ContentAgent to worker.py and update scheduler wiring test** — `8c20007` (feat)

## Files Created/Modified

- `scheduler/agents/content_agent.py` — ~520 lines; adds RSS_FEEDS, SERPAPI_KEYWORDS constants, _get_config, _fetch_all_rss, _fetch_all_serpapi, _score_relevance, _run_pipeline (10-step pipeline), run(), _extract_check_text module-level helper
- `scheduler/worker.py` — adds `from agents.content_agent import ContentAgent` import; adds `elif job_name == "content_agent"` branch to _make_job()
- `scheduler/tests/test_content_agent.py` — replaces test_rss_feed_parsing and test_serpapi_parsing stubs with real assertions; removes skip guard from test_scheduler_wiring; all 16 tests active

## Decisions Made

- `RSS_FEEDS` and `SERPAPI_KEYWORDS` as module-level constants (not class attributes) — consistent with plan spec; accessible as `ca.RSS_FEEDS` in tests without instantiation
- `run()` commits AgentRun immediately before pipeline starts so status=running is visible in DB even if pipeline crashes
- Lazy imports for `ContentBundle` and `process_new_items` inside `_run_pipeline` — avoids circular import issues (same pattern used throughout codebase)
- `_extract_check_text` is module-level (not class method) — consistent with established pattern for testable pure functions

## Deviations from Plan

None — plan executed exactly as written. Both tasks completed with all 16 tests GREEN.

## Known Stubs

None — all stubs from Plans 02-04 have been replaced with full implementations in this plan. The `parse_rss_entries()` and `parse_serpapi_results()` module-level stub functions still exist in the file but are superseded by `_fetch_all_rss()` and `_fetch_all_serpapi()` class methods. They are unused placeholders and do not affect pipeline operation.

## Self-Check: PASSED

- `scheduler/agents/content_agent.py` exists with `_run_pipeline`, `run()`, `_fetch_all_rss`, `_fetch_all_serpapi`, `_score_relevance`, `_get_config`, `_extract_check_text`, `feedparser.parse`, `run_in_executor`, `asyncio.gather`, `process_new_items`, `agent_run.items_found`, `agent_run.items_queued`, `kitco.com/rss/news.xml`, `"gold exploration"` all present
- `scheduler/worker.py` contains `from agents.content_agent import ContentAgent` and `elif job_name == "content_agent"`
- Commits `87a678a` and `8c20007` present in git log
- All 16 tests GREEN confirmed: `16 passed in 0.34s`

---
*Phase: 07-content-agent*
*Completed: 2026-04-02*
