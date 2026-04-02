---
phase: 07-content-agent
plan: 02
subsystem: scheduler
tags: [content-agent, tdd, scoring, deduplication, pure-functions, python]

# Dependency graph
requires:
  - phase: 07-01
    provides: Wave 0 test stubs, ContentBundle model, feedparser/serpapi/httpx deps
provides:
  - scheduler/agents/content_agent.py — pure scoring, dedup, and selection functions
  - recency_score, credibility_score, calculate_story_score, deduplicate_stories, select_top_story
  - ContentAgent class skeleton with __init__ (run() stub for Plan 05)
affects:
  - 07-03 through 07-05 (all plans build on top of content_agent.py)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - TDD RED/GREEN: remove pytest.skip() guards to activate tests, then implement
    - difflib.SequenceMatcher for headline similarity dedup (ratio >= 0.85)
    - Module-level pure functions for direct testability (same pattern as instagram_agent.py)
    - CREDIBILITY_TIERS dict as module-level constant — single source of truth for credibility lookup

key-files:
  created:
    - scheduler/agents/content_agent.py
  modified:
    - scheduler/tests/test_content_agent.py

key-decisions:
  - "URL deduplication uses seen set, keeps first occurrence — O(n) with no credibility tiebreak (first=wins)"
  - "Headline similarity uses difflib.SequenceMatcher on lowercased titles — case-insensitive, no external dep"
  - "select_top_story threshold is strictly exclusive (score > threshold, not >=) — consistent with 7.0/10 quality bar language"
  - "ContentAgent.run() is a stub (pass) — full pipeline wired in Plan 05 per implementation spec"

# Metrics
duration: 3min
completed: 2026-04-02
---

# Phase 7 Plan 02: Ingest-Dedup-Score Pipeline Summary

**Pure scoring, dedup, and selection functions implemented via TDD — recency/credibility/formula scoring, URL+headline dedup with credibility tiebreak, threshold-based top-story selection; 7 tests GREEN, 9 Wave 0 stubs remain SKIPPED**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-02T23:23:18Z
- **Completed:** 2026-04-02T23:26:10Z
- **Tasks:** 2 (TDD RED + TDD GREEN)
- **Files modified:** 2

## Accomplishments

- Activated 7 failing tests (TDD RED) by removing pytest.skip() guards from recency, credibility, formula, URL dedup, headline dedup, select top story, and no-story flag tests
- Implemented `scheduler/agents/content_agent.py` with 5 pure functions + ContentAgent skeleton (220 lines, above 100-line minimum)
- All 7 target tests GREEN; 9 remaining Wave 0 stubs still SKIPPED (for Plans 03-05)
- `difflib.SequenceMatcher` headline dedup correctly keeps more credible source (reuters.com over kitco.com) when ratio >= 0.85
- Score formula verified: `calculate_story_score(0.9, 1.0, 0.8)` returns exactly 9.0

## Task Commits

1. **TDD RED: activate 7 failing tests** — `0d9f736` (test)
2. **TDD GREEN: implement pure functions** — `d44cc91` (feat)

## Files Created/Modified

- `scheduler/agents/content_agent.py` — 220 lines; exports recency_score, credibility_score, calculate_story_score, deduplicate_stories, select_top_story, ContentAgent class
- `scheduler/tests/test_content_agent.py` — removed 7 pytest.skip() guards; 7 tests now active, 9 remain skipped

## Decisions Made

- URL deduplication keeps first occurrence — simple O(n) set lookup, no credibility tiebreak needed for exact URL matches
- Headline similarity uses `difflib.SequenceMatcher` on lowercased titles — no external fuzzy matching library needed
- `select_top_story` threshold is strictly exclusive (`score > threshold`) — consistent with spec language "above 7.0/10"
- `ContentAgent.run()` is a pass stub — full pipeline wired in Plan 05 per implementation spec directive

## Deviations from Plan

None — plan executed exactly as written. Both TDD phases completed: RED (7 tests activated/failing), GREEN (implementation makes all 7 pass).

## Known Stubs

- `parse_rss_entries()` — returns `[]`, full RSS parsing implementation in Plan 03
- `parse_serpapi_results()` — returns `[]`, full SerpAPI parsing implementation in Plan 03
- `ContentAgent.run()` — `pass` stub, full pipeline in Plan 05

These stubs do not affect Plan 02 goal (pure function tests) — they are intentional placeholders for Plans 03 and 05.

## Self-Check: PASSED

- `scheduler/agents/content_agent.py` exists (220 lines)
- `scheduler/tests/test_content_agent.py` modified (7 skip guards removed)
- Commits `0d9f736` and `d44cc91` verified in git log
- All 7 target tests GREEN confirmed: `7 passed, 9 skipped in 0.29s`

---
*Phase: 07-content-agent*
*Completed: 2026-04-02*
