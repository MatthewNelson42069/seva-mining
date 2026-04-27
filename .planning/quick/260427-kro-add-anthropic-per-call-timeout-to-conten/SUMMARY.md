# Quick Task 260427-kro — fetch_stories cache-lock deadlock fix — SUMMARY

**Shipped:** 2026-04-27
**Branch:** `main` (no quick-task branch — single-line defensive fix)

## Why

User asked: *"is breaking news 100% working. it hasn't pulled anything in its last 6 runs"*

Investigation traced 8 status='failed' agent_runs rows over a 5h window — all stamped with `ended_at = 21:47:26` (single scheduler restart) and the standard adoption marker `"scheduler restart — run abandoned (process killed before finally block)"`. Pattern: every agent that calls `content_agent.fetch_stories()` (`sub_breaking_news`, `sub_threads`, `sub_infographics`, `sub_quotes`) was stuck for hours. Every agent that doesn't (`sub_gold_history`, `sub_gold_media`, `morning_digest`) completed normally during the same window.

## Root cause

`fetch_stories()` at `scheduler/agents/content_agent.py:1037` holds an asyncio.Lock (`_CACHE_LOCK`) while:
1. Sequentially calling `_score_relevance` (~120 Anthropic Haiku calls)
2. Then `gather()`ing `classify_format_lightweight` (~120 more Haiku calls)

The `AsyncAnthropic` client at line 1083 was constructed with NO `timeout` parameter, inheriting the SDK default of **600 seconds per call**. When Anthropic API is slow (or returns a hung connection), one call can block for up to 10 minutes. With the cache lock held the entire time, every subsequent caller of `fetch_stories()` — every text-pipeline agent — blocks until the worker dies and Railway restarts it.

The 16:24 UTC breaking_news run was the last one to acquire the lock cleanly. After that, one of the 120+ Haiku calls hung. The lock stayed held for 5+ hours. 8 agent runs queued behind it. Eventually Railway killed the worker; the new worker's reconcile_stale_runs swept all 8 orphans at 21:47:26.

## Fix

Single-line change at `scheduler/agents/content_agent.py:1083` — set `timeout=30.0` on the `AsyncAnthropic` constructor:

```python
anthropic_client = AsyncAnthropic(
    api_key=settings.anthropic_api_key, timeout=30.0
)
```

30 seconds is plenty for Haiku scoring/classification (typical: 1-2s). On a hang:
- Anthropic SDK raises `APITimeoutError` after 30s
- `_score_relevance` already has a try/except → routes to `_keyword_relevance` keyword fallback
- `classify_format_lightweight` gather already has a try/except → routes to default `"thread"` predicted_format
- The lock is released normally; subsequent callers retry on the next 30-min cache bucket
- Net effect: a slow Anthropic API degrades to keyword scoring; never blocks the whole pipeline

## What this does NOT touch

- The 2 other `AsyncAnthropic` instantiations in this file (lines 386, 441) — they're per-call clients used by compliance review + gold-gate, not the deadlock culprits
- The `AsyncAnthropic` clients in each per-agent drafter (`scheduler/agents/content/*.py`) — those use Sonnet for drafting and may legitimately need longer; out of scope
- The cache structure or `_CACHE_LOCK` semantics — kept as-is

## Validation

- `cd scheduler && uv run pytest -x` → **184 passed** (no behavior change on happy path)
- `cd scheduler && uv run ruff check .` → clean
- Preservation: the only change is the constructor call site at line 1083; no other diffs in `content_agent.py` or any other file
- Manual: existing tests don't cover this code path against a real Anthropic timeout, but the fallback paths (`_score_relevance` keyword fallback + classifier `"thread"` default) are already tested

## Operational impact

After Railway picks this up:
- The current stuck `running` rows (21:24 + 21:47) will be swept by the redeploy's `reconcile_stale_runs`
- The new worker's first `fetch_stories()` cache-miss will run with the 30s/call cap
- Worst case if Anthropic is slow: ~120 calls × 30s = 60 min total fetch_stories runtime — but each call individually fails fast and the defensive paths return reasonable defaults (keyword scoring + thread classification)
- Best case: no hangs, no behavior change
- Either way: no agent gets blocked for >60 min waiting on the lock

## Follow-ups (not in this task)

- Parallelize the `_score_relevance` loop (currently sequential `for`) into `asyncio.gather()` — would cut worst-case from 60 min to 30s. Larger refactor; deferred.
- Add an outer `asyncio.wait_for(..., timeout=600)` watchdog around the whole cache-miss block — belt-and-suspenders. Deferred until we see another hang in prod.
- Consider lowering the Anthropic SDK default timeout for OTHER `AsyncAnthropic` instantiations in the codebase (per-agent drafters use 600s default; if Sonnet hangs there, the per-agent run hangs but doesn't block other agents because no shared lock).
