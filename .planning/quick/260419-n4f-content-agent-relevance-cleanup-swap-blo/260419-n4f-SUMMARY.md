---
phase: quick-260419-n4f
plan: 01
subsystem: scheduler/content-agent
tags: [content-agent, relevance, rss-feeds, gold-gate, tdd]
key-files:
  modified:
    - scheduler/agents/content_agent.py
    - scheduler/seed_content_data.py
    - scheduler/worker.py
    - scheduler/tests/test_content_agent.py
decisions:
  - "Two-bucket LLM gate uses Haiku at max_tokens=5 (yes/no response) — minimal cost per story checked"
  - "Fail-open on API error: gate returns True so infra blips never silence real gold stories"
  - "Gate bypassed when content_gold_gate_enabled=False — operator can disable without code change"
  - "content_quality_threshold restored to 7.0 — feed narrowing + gate replace the 5.5 workaround"
  - "Investing.com removed from RSS_FEEDS but kept in CREDIBILITY_TIERS — SerpAPI may still surface it"
metrics:
  duration: "~12 minutes"
  completed: "2026-04-19"
  tasks: 3
  files: 4
---

# Quick Task 260419-n4f: Content Agent Relevance Cleanup Summary

**One-liner:** Narrowed Bloomberg RSS to commodities feed, dropped Investing.com RSS, sharpened relevance prompt with explicit gold/systemic score bands, and added two-bucket Haiku gold gate that hard-rejects generic finance articles post-scoring.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Feed list cleanup + module docstring update | 502ae3e | scheduler/agents/content_agent.py |
| 2 | Sharpen relevance scoring prompt | 010926d | scheduler/agents/content_agent.py |
| 3 | Two-bucket gold gate + config knobs + threshold restore + tests | 2cfc9cb | content_agent.py, seed_content_data.py, worker.py, tests/test_content_agent.py |

## Changes Made

### Task 1: Feed List Cleanup
- Bloomberg URL changed from `feeds.bloomberg.com/markets/news.rss` to `feeds.bloomberg.com/commodities/news.rss`
- `investing.com` RSS feed removed — was surfacing generic finance articles unrelated to gold
- RSS_FEEDS reduced from 8 to 7 entries
- Module docstring updated to reflect current feed list (Bloomberg now described as commodities feed)
- CREDIBILITY_TIERS entry for `investing.com` preserved (SerpAPI fallback may still surface investing.com articles)

### Task 2: Sharpened Relevance Prompt
- Replaced flat "rate 0-1" prompt with three explicit score bands:
  - 0.7–1.0: Direct gold/precious metals/mining/ETF/central bank content
  - 0.5–0.8: Systemic shocks that move gold (Strait of Hormuz, Fed/USD, war escalation, oil supply, currency crisis)
  - 0.0–0.3: Generic business, option traders, private credit, clickbait with no gold angle
- Parser compatibility retained ("Reply with only a decimal number")

### Task 3: Two-Bucket Gold Gate
- New module-level `is_gold_relevant_or_systemic_shock(story, config, client)` function added after `check_compliance`
- Gate uses Haiku at max_tokens=5 for minimal cost — yes/no response only
- Fail-open: catches all exceptions, returns True so infra blips never drop real gold stories
- Bypassed when `content_gold_gate_enabled` is "false"/"0"/"no" in config
- Gate inserted in `_run_pipeline` loop after `already_covered` check, before `fetch_article`
- `skipped_by_gate` counter logged per-rejection and as run summary
- `content_quality_threshold` restored to "7.0" in worker.py (was "5.5" workaround)
- `content_gold_gate_enabled=true` and `content_gold_gate_model=claude-3-5-haiku-latest` added to seed_content_data.py CONFIG_DEFAULTS
- 6 new gate tests added via TDD (RED then GREEN)
- `test_rss_feed_parsing` updated: assert 7 feeds (was 8)

## Test Results

- scheduler: 104 passed, 1 warning (SAWarning on test_worker.py — pre-existing, unrelated)
- backend: 71 passed, 5 skipped, 15 warnings (unchanged)
- ruff: 0 errors on scheduler/

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Unused import `APIError` in test_gate_fails_open_on_api_error**
- **Found during:** Task 3, post-implementation ruff check
- **Issue:** The plan included `from anthropic import APIError` in the test body but the comment in the test explains a generic Exception is used instead (APIError requires a `request=` param). Ruff flagged this as F401.
- **Fix:** Removed the unused `from anthropic import APIError` import line from the test
- **Files modified:** scheduler/tests/test_content_agent.py
- **Commit:** 2cfc9cb (included in Task 3 commit)

## Known Stubs

None — all changes are functional implementations with no placeholder data.

## Self-Check: PASSED

- scheduler/agents/content_agent.py: FOUND (modified)
- scheduler/seed_content_data.py: FOUND (modified)
- scheduler/worker.py: FOUND (modified)
- scheduler/tests/test_content_agent.py: FOUND (modified)
- Commit 502ae3e: FOUND
- Commit 010926d: FOUND
- Commit 2cfc9cb: FOUND
- 104 scheduler tests: PASSED
- 71 backend tests: PASSED
- ruff check: CLEAN
