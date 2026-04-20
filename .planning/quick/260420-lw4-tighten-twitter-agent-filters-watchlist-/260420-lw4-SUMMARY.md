---
phase: quick-260420-lw4
plan: 01
subsystem: scheduler/twitter-agent
tags: [twitter, filters, engagement-gate, gold-keywords, quality, watchlist]
dependency_graph:
  requires: []
  provides:
    - "Twitter agent: watchlist-only ingestion (no keyword-search path)"
    - "Twitter agent: literal GOLD_KEYWORDS topic filter (no Sonnet fallback)"
    - "Twitter agent: 50-like engagement floor on both general + watchlist paths"
    - "Twitter agent: GoldTelegraph_ universal bypass of topic filter + engagement gate"
  affects:
    - scheduler/worker.py
    - scheduler/agents/twitter_agent.py
    - scheduler/tests/test_twitter_agent.py
tech_stack:
  added: []
  patterns:
    - "ALWAYS_ENGAGE_HANDLES frozenset for per-account filter bypass"
    - "Operator-rule comment convention quick-YYYYMMDD-XXX in config overrides"
key_files:
  created: []
  modified:
    - scheduler/worker.py
    - scheduler/agents/twitter_agent.py
    - scheduler/tests/test_twitter_agent.py
decisions:
  - "OP-LW4-01: watchlist-only ingestion — _fetch_keyword_tweets and _build_keyword_queries deleted"
  - "OP-LW4-02: literal GOLD_KEYWORDS match only — Sonnet gold-adjacency fallback removed from _apply_topic_filter"
  - "OP-LW4-03: twitter_min_likes_general=50 (was 5), twitter_min_likes_watchlist=50 (was 0)"
  - "OP-LW4-04: ALWAYS_ENGAGE_HANDLES frozenset{goldtelegraph_} bypasses both topic filter and engagement gate; bypass logged per-tweet for Railway observability"
metrics:
  duration: "~15 min"
  completed: "2026-04-20"
  tasks: 2
  files: 3
---

# Quick Task 260420-lw4: Tighten Twitter Agent Filters + Gold Telegraph Bypass

**One-liner:** Watchlist-only ingestion with literal GOLD_KEYWORDS topic filter, 50-like floor on both paths, and ALWAYS_ENGAGE_HANDLES frozenset giving @GoldTelegraph_ unconditional bypass of both filters.

## Context

Operator reported queue contaminated with garbage: `EddieMoore25674` spam account tweets and Reuters stories about Hormuz/India rupee (no gold mentions). Root cause analysis found three compounding bugs:

1. `twitter_min_likes_general` was 5 (too relaxed); `twitter_min_likes_watchlist` was 0 (completely open).
2. `_apply_topic_filter` called Sonnet for watchlist tweets that failed the literal keyword check — allowing off-topic content via LLM judgment.
3. `_fetch_keyword_tweets` and `_build_keyword_queries` remained in the codebase but were unused — dead code and source of confusion.

Operator added a fourth explicit rule: @GoldTelegraph_ is our highest-signal watchlist source and must be ingested unconditionally regardless of gold-keyword presence or like count.

## Tasks Completed

### Task 1: Raise engagement gate floor in worker.py to 50 likes

Commit: `18c0701`

Changed in `upsert_agent_config()`:
- `"twitter_min_likes_general": "5"` → `"50"`
- `"twitter_min_likes_watchlist": "0"` → `"50"`

Both entries now carry operator-rule comments referencing `260420-lw4`. Views thresholds left at `"0"` (Basic tier never returns `impression_count`).

### Task 2: Remove keyword-search path and Sonnet topic-filter fallback

Commit: `b6cee40`

**scheduler/agents/twitter_agent.py changes:**
- Removed `from models.keyword import Keyword` import
- Added `ALWAYS_ENGAGE_HANDLES: frozenset[str] = frozenset({"goldtelegraph_"})` constant after `GOLD_KEYWORDS`
- Deleted `_load_keywords()` method entirely
- Deleted `_fetch_keyword_tweets()` method entirely
- Deleted `_build_keyword_queries()` method entirely
- Rewrote `_apply_topic_filter()` to literal GOLD_KEYWORDS scan only (no `self.anthropic.messages.create` call)
- `_run_pipeline` Step 3: removed `keywords = await self._load_keywords(session)`, updated log line
- `_run_pipeline` Step 5: `all_tweets = watchlist_tweets` (no dedup block)
- `_run_pipeline` Step 6: ALWAYS_ENGAGE_HANDLES bypass before `_apply_topic_filter` with per-tweet log line
- `_run_pipeline` Step 7: ALWAYS_ENGAGE_HANDLES bypass before `passes_engagement_gate` with per-tweet log line

**scheduler/tests/test_twitter_agent.py changes:**
- Removed three dead `patch.object(agent, "_fetch_keyword_tweets", return_value=[])` lines (from `test_twitter_whatsapp_notification_fires_when_items_queued`, `_skipped_when_no_items`, and `_failure_is_non_fatal`)
- Also removed dead `patch.object(agent, "_load_keywords", return_value=[])` from those same tests
- Added `test_always_engage_handles_constant` — asserts `"goldtelegraph_" in ALWAYS_ENGAGE_HANDLES`
- Added `test_gold_telegraph_bypasses_topic_and_engagement_filters` — runs pipeline with two tweets (GoldTelegraph_: 0 likes, no gold text; Reuters: 0 likes, no gold text), asserts only GoldTelegraph_ reaches `_score_tweet`, asserts bypass log lines appear in caplog

## Verification

- `pytest tests/test_twitter_agent.py -x`: 25 passed
- `ruff check scheduler/`: All checks passed
- `python -c "... assert not hasattr(TwitterAgent, '_fetch_keyword_tweets') ..."`: attributes removed OK
- `grep -c '_fetch_keyword_tweets|_build_keyword_queries|_load_keywords' scheduler/agents/twitter_agent.py`: 0
- `grep -c 'ALWAYS_ENGAGE_HANDLES' scheduler/agents/twitter_agent.py`: 7 (>= 3 required)
- `grep '"twitter_min_likes_(general|watchlist)": "50"' scheduler/worker.py`: 2 matches

## Deviations from Plan

None — plan executed exactly as written.

## Task 3: Pending Checkpoint

Task 3 (`checkpoint:human-verify`) is a post-deploy DB spot-check that requires Railway redeployment and production DB access. This task is intentionally left to the operator.

**What to do after merging and Railway redeploys:**

1. Wait for at least one full `twitter_agent` cron cycle (every 2h). Confirm Railway logs show: `TwitterAgent: engagement thresholds — general: 50 likes/0 views, watchlist: 50 likes/0 views`
2. Run the spot-check query against production DB (see Task 3 in the PLAN.md for the exact SQL).
3. Verify the 10 most recent `platform='twitter'` rows:
   - Every row's `source_account` is in the active watchlist
   - Every non-GoldTelegraph_ row contains a GOLD_KEYWORDS term in `text_preview`
   - Every non-GoldTelegraph_ row has `likes >= 50`
   - GoldTelegraph_ rows are exempt from keyword/likes checks
4. Also spot-check Railway logs for the new watchlist-only ingestion log line and the "always-engage bypass" lines for any GoldTelegraph_ tweets.
5. Reply `approved` in the plan thread if all checks pass.

## Self-Check: PASSED

- `/Users/matthewnelson/seva-mining/scheduler/worker.py` — FOUND
- `/Users/matthewnelson/seva-mining/scheduler/agents/twitter_agent.py` — FOUND
- `/Users/matthewnelson/seva-mining/scheduler/tests/test_twitter_agent.py` — FOUND
- Commit `18c0701` — FOUND (Task 1)
- Commit `b6cee40` — FOUND (Task 2)
