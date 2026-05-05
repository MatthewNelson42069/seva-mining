---
phase: 07-content-agent
plan: "07"
subsystem: content-agent
tags: [content-agent, breaking-news, multi-story, rss-expansion, cross-run-dedup, serpapi-expansion]
dependency_graph:
  requires: [07-06]
  provides: [breaking-news-format, multi-story-pipeline, cross-run-dedup, expanded-rss-8, expanded-keywords-10]
  affects: [scheduler/agents/content_agent.py]
tech_stack:
  added: []
  patterns: [multi-story-pipeline, cross-run-dedup, per-story-error-isolation]
key_files:
  created: []
  modified:
    - scheduler/agents/content_agent.py
decisions:
  - "RSS_FEEDS expanded from 4 to 8 including reuters.com, bloomberg.com, goldseek.com, investing.com"
  - "SERPAPI_KEYWORDS expanded from 6 to 10 with macro/inflation terms"
  - "select_top_story() retained alongside select_qualifying_stories() for backward compatibility"
  - "breaking_news format added as 4th Sonnet format option with urgency-preference instruction in system prompt"
  - "_is_already_covered_today() uses today UTC date + URL exact match + headline similarity >= 0.85 via difflib"
  - "Multi-story pipeline: all qualifying stories processed per run with per-story try/except isolation"
  - "all_already_covered sentinel flag: creates no-story bundle with descriptive note if all qualifying were already covered"
metrics:
  duration: "~10 minutes"
  completed: "2026-04-07"
  tasks_completed: 2
  files_modified: 1
---

# Phase 07 Plan 07: Breaking News + Multi-Story Pipeline Summary

Extended content agent with breaking_news format (1-3 line ALL CAPS urgent tweets), expanded RSS feeds from 4 to 8 and SerpAPI keywords from 6 to 10, added cross-run deduplication via `_is_already_covered_today()`, and converted the pipeline from single-story to multi-story output with per-story error isolation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Expand sourcing constants + credibility tiers + cross-run dedup + multi-story selection | e8c1fb8 | scheduler/agents/content_agent.py |
| 2 | Breaking news format + Sonnet prompt expansion + compliance/DraftItem extension | e3215f1 | scheduler/agents/content_agent.py |

## Decisions Made

- **8 RSS feeds**: Added reuters.com, bloomberg.com, goldseek.com, investing.com to existing 4. Bloomberg URL `https://feeds.bloomberg.com/markets/news.rss` used — agent continues on feed failure per existing error handling.
- **10 SerpAPI keywords**: Added "gold inflation hedge", "Fed gold", "dollar gold", "recession gold" to existing 6 macro keywords.
- **Backward compatibility**: `select_top_story()` retained alongside new `select_qualifying_stories()` — existing tests reference it.
- **Cross-run dedup**: `_is_already_covered_today()` queries today's ContentBundle records (UTC date, no_story_flag=False), checks URL exact match and headline similarity >= 0.85.
- **Multi-story error isolation**: Each qualifying story wrapped in try/except — individual story failures log error but do not abort remaining stories.
- **All-covered edge case**: If every qualifying story was already in an earlier run, creates no-story bundle with note "All qualifying stories already covered in earlier run".
- **Breaking news format**: Added as 4th option in Sonnet prompt with description "1-3 punchy lines, ALL CAPS for key terms, no hashtags". System prompt instructs Claude to prefer breaking_news for urgent stories (major price moves, major announcements).
- **Senior analyst voice**: Added to system prompt — "First line is always the most impactful data point. Lead with the number. Surface ONE non-obvious insight not in the original article."

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all logic is fully wired. The bloomberg.com RSS URL (`https://feeds.bloomberg.com/markets/news.rss`) is a best-effort URL per the plan note "verify at implementation, log warning if feed fails". The existing error handling in `_fetch_all_rss()` already covers this: feed failure logs a warning and continues, not aborting the run.

## Self-Check: PASSED

- [x] `scheduler/agents/content_agent.py` has `len(RSS_FEEDS) == 8` — VERIFIED
- [x] `scheduler/agents/content_agent.py` has `len(SERPAPI_KEYWORDS) == 10` — VERIFIED
- [x] `CREDIBILITY_TIERS` includes `goldseek.com: 0.6` and `investing.com: 0.6` — VERIFIED
- [x] `select_qualifying_stories()` exists and returns all stories above threshold sorted descending — VERIFIED
- [x] `_is_already_covered_today()` method exists on ContentAgent, queries ContentBundle by date — VERIFIED
- [x] `_run_pipeline()` processes all qualifying stories with per-story error isolation — VERIFIED
- [x] `_extract_check_text()` handles `breaking_news` format — VERIFIED
- [x] `build_draft_item()` handles `breaking_news` format — VERIFIED
- [x] Sonnet prompt includes 4 format options including `breaking_news` — VERIFIED
- [x] Commit e8c1fb8 — FOUND
- [x] Commit e3215f1 — FOUND
