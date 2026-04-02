---
phase: 07-content-agent
plan: 03
subsystem: scheduler
tags: [content-agent, httpx, beautifulsoup, serpapi, claude-sonnet, deep-research, python]

# Dependency graph
requires:
  - phase: 07-02
    provides: ContentAgent class skeleton with __init__, pure scoring functions, test infrastructure

provides:
  - scheduler/agents/content_agent.py — extract_article_text, fetch_article, _search_corroborating, _research_and_draft
  - Article fetch with paywall/error fallback via httpx + BeautifulSoup extraction
  - SerpAPI Google News corroboration search (run_in_executor for sync client)
  - Combined Claude Sonnet prompt for format decision (thread/long_form/infographic) + drafting

affects:
  - 07-04 (RSS/SerpAPI ingestion builds on same file)
  - 07-05 (pipeline wiring calls _research_and_draft and _search_corroborating)

# Tech tracking
tech-stack:
  added:
    - httpx (AsyncClient for article fetching)
    - beautifulsoup4 (bs4 for HTML article extraction)
    - serpapi (synchronous client wrapped in run_in_executor)
  patterns:
    - extract_article_text is module-level pure function for direct testability
    - fetch_article is module-level async function — tuple return (text, success_flag) for explicit fallback signaling
    - serpapi synchronous call wrapped in asyncio.run_in_executor(None, _call) to avoid blocking event loop
    - Combined format-decision + drafting in single Sonnet call — reduces latency and API cost vs two separate calls
    - JSON response with markdown fence stripping for robustness

key-files:
  created: []
  modified:
    - scheduler/agents/content_agent.py
    - scheduler/tests/test_content_agent.py

key-decisions:
  - "fetch_article returns (fallback_text, False) on any failure — explicit success flag avoids caller having to infer from empty string"
  - "extract_article_text tries semantic selectors in priority order then falls back to full body text — handles variety of article structures gracefully"
  - "serpapi Client runs in executor — serpapi library is synchronous, run_in_executor avoids blocking the async event loop"
  - "_research_and_draft makes one combined Sonnet call for format decision + drafting — reduces API calls from 2 to 1 per pipeline run"
  - "JSON parse failure in _research_and_draft returns None — caller (Plan 05 pipeline) handles as pipeline failure, not silent empty draft"

patterns-established:
  - "Tuple return (value, success_bool) pattern for operations with graceful fallback"
  - "Module-level async functions for testability without class instantiation"
  - "Markdown code fence stripping before JSON parsing for LLM response robustness"

requirements-completed: [CONT-08, CONT-09, CONT-10, CONT-11, CONT-12, CONT-13]

# Metrics
duration: 2min
completed: 2026-04-02
---

# Phase 7 Plan 03: Deep Research Pipeline Summary

**httpx article fetch with BeautifulSoup extraction, SerpAPI corroboration search in executor, and combined Claude Sonnet prompt producing thread/long_form/infographic drafts in a single API call**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-02T23:28:23Z
- **Completed:** 2026-04-02T23:30:37Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Implemented `extract_article_text()` — strips nav/header/footer/aside/script/style boilerplate, tries semantic selectors (article, main, [role='main'], div.content, div.article-body), falls back to full body text
- Implemented `fetch_article()` — async httpx fetch with 15s timeout, User-Agent header, explicit fallback on non-200, <100 char extraction, or any exception; returns (text, success_flag) tuple
- Implemented `ContentAgent._search_corroborating()` — SerpAPI Google News search via run_in_executor (synchronous client wrapped), returns 2-3 result dicts; empty list on failure
- Implemented `ContentAgent._research_and_draft()` — single Claude Sonnet call with full research bundle; format decision + drafting + key_data_points extraction; returns None on JSON parse failure
- Updated `ContentAgent.__init__` to include `serpapi.Client(api_key=settings.serpapi_api_key)`
- `test_article_fetch_fallback` and `test_thread_draft_structure` both GREEN; full test suite: 9 passed, 7 skipped

## Task Commits

1. **Task 1: Article fetch, BeautifulSoup extraction, corroboration search** — `ef47f92` (feat)
2. **Task 2: Combined Claude Sonnet format-decision + drafting pipeline** — `40b4020` (feat)

## Files Created/Modified

- `scheduler/agents/content_agent.py` — 397 lines; adds extract_article_text, fetch_article, _search_corroborating, _research_and_draft, serpapi.Client in __init__
- `scheduler/tests/test_content_agent.py` — removes 2 more skip guards (test_article_fetch_fallback, test_thread_draft_structure); 9 tests now active, 7 remain skipped

## Decisions Made

- `fetch_article` returns `(fallback_text, False)` on any failure — explicit success flag vs empty string sentinel avoids ambiguity when article genuinely has very short text
- `serpapi` synchronous client runs in `asyncio.run_in_executor(None, _call)` — standard pattern for wrapping sync I/O in async context without blocking the event loop
- Single combined Sonnet call for format decision + drafting — reduces API latency and cost vs 2 separate calls; Claude can use full research context for both decisions simultaneously
- `_research_and_draft` returns `None` on JSON parse failure — Plan 05 pipeline caller must handle None explicitly; silent empty dict would hide failures

## Deviations from Plan

None — plan executed exactly as written. Both tasks completed with tests GREEN.

## Known Stubs

- `parse_rss_entries()` — returns `[]`, full RSS parsing implementation in Plan 04
- `parse_serpapi_results()` — returns `[]`, full SerpAPI parsing implementation in Plan 04
- `ContentAgent.run()` — `pass` stub, full pipeline in Plan 05

These stubs do not affect Plan 03 goal (deep research + drafting functions) — they are intentional placeholders for Plans 04 and 05.

## Self-Check: PASSED

- `scheduler/agents/content_agent.py` exists (397 lines, above 250-line minimum)
- `scheduler/tests/test_content_agent.py` modified (2 skip guards removed)
- Commits `ef47f92` and `40b4020` verified in git log
- Both target tests GREEN confirmed: `9 passed, 7 skipped in 0.32s`
- All acceptance criteria verified: extract_article_text, fetch_article, BeautifulSoup(html, httpx.AsyncClient, _search_corroborating, serpapi.Client, run_in_executor, fallback_text, _research_and_draft, claude-sonnet-4-20250514, senior gold market analyst, You never mention Seva Mining, You never give financial advice, thread/long_form/infographic, key_data_points, max_tokens all present in file

---
*Phase: 07-content-agent*
*Completed: 2026-04-02*
