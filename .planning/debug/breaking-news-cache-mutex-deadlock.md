---
status: awaiting_human_verify
trigger: "sub_breaking_news (and other fetch_stories-using agents) intermittently hang forever after the first 1–3 successful runs in a fresh process. The hang holds an asyncio cache mutex, blocking all subsequent fetch_stories-using agents (sub_threads, sub_infographics, sub_quotes) until Railway redeploys."
created: 2026-04-27T00:00:00Z
updated: 2026-04-27T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED. Sequential _score_relevance loop (lines 1131-1138) runs INSIDE async with _CACHE_LOCK, making one Anthropic call per story for all ~118-119 unique stories. With 30s timeout, worst case = 118 × 30s = 3,540s (59 min) while holding the lock. All other agents calling fetch_stories() block on _CACHE_LOCK the entire time. This is "starvation" not a true deadlock — one long-held lock, not a circular wait.
test: DB evidence: 7:01 run shows items_found=0, notes=NULL (never returned from fetch_stories), ran for 33,802s before being swept. 19:00 sub_infographics, sub_quotes, sub_breaking_news all hung simultaneously (DB shows all 4 agents starting at ~19:00-19:24 all failed by restart) — confirms lock contention cascades to all fetch_stories-using agents.
expecting: Fix: run _score_relevance calls OUTSIDE the lock, OR parallelize with asyncio.gather, OR use coalesce pattern (single in-flight Future)
next_action: Implement fix — move scoring loop outside the lock

## Symptoms

expected: sub_breaking_news completes each run in 4–6 minutes. Other fetch_stories-using agents complete in similar time frames.
actual: A run goes "running" in agent_runs and never reaches the finally-block JSON write — notes stays NULL, items_found=0, items_queued=0. While hung, the asyncio cache mutex in fetch_stories appears held — concurrent agents also hang and get reconcile-swept on next Railway restart.
errors: No exceptions in run rows. Hung runs are silent. Reconcile sweeps mark them failed with "scheduler restart — run abandoned (process killed before finally block)"
reproduction: Wait for Railway redeploy, observe pattern: 1-3 successful runs then indefinite hang until next restart
started: First observed 2026-04-22. kro fix (AsyncAnthropic timeout=30.0, commit f02b423) shipped 2026-04-26 — confirmed live but deadlock still occurs.

## Eliminated

- hypothesis: True deadlock (circular wait) between two coroutines
  evidence: No circular wait. Single lock, single long-held holder. It is lock starvation.
  timestamp: 2026-04-27T00:05:00Z

- hypothesis: Bug is outside fetch_stories (in drafting loop of sub_breaking_news)
  evidence: items_found=0 in all hung runs means fetch_stories() itself never returned. agent_run.items_found is set immediately after fetch_stories() returns (line 178 of __init__.py). If it were hanging post-fetch, items_found would be >0.
  timestamp: 2026-04-27T00:05:00Z

- hypothesis: Lock is per-bucket (so different buckets don't contend)
  evidence: _CACHE_LOCK is a single module-level asyncio.Lock(), not per-bucket. All callers share one lock regardless of which 30-min bucket they target.
  timestamp: 2026-04-27T00:05:00Z

## Evidence

- timestamp: 2026-04-27T00:00:00Z
  checked: kro fix commit f02b423 (lines 1082-1095 of content_agent.py)
  found: Added timeout=30.0 to AsyncAnthropic() client inside the locked section. Lock acquisition at line 1071 (async with _CACHE_LOCK).
  implication: timeout=30.0 fires per individual Anthropic call. With 118-119 stories (observed from completed runs: "candidates": 118/119), worst-case locked time = 118 × 30s = 3,540s. Does not fix root cause.

- timestamp: 2026-04-27T00:05:00Z
  checked: lines 1126-1153 of content_agent.py — ALL inside async with _CACHE_LOCK block
  found: Sequential for loop calling await _score_relevance() (lines 1131-1138) for every unique story, then asyncio.gather over classify_format_lightweight (line 1142) — ALL inside the lock. The scoring loop is strictly sequential (one await per iteration), so every story's Anthropic call must complete before the next begins.
  implication: 118 sequential Anthropic calls inside the lock. If Anthropic is slow (10s/call average) → 20 minutes of lock held. If any call approaches the 30s timeout → 59 minutes worst case.

- timestamp: 2026-04-27T00:07:00Z
  checked: DB evidence — hung runs with items_found=0, notes=NULL
  found: sub_breaking_news 7:01 UTC: items_found=0, notes=NULL, ran 33,802s. sub_infographics 19:00: items_found=0, notes=NULL. sub_quotes 19:00: items_found=0, notes=NULL. sub_breaking_news 19:24: items_found=0, notes=NULL. All other agents behind same lock simultaneously hung — confirms cascade.
  implication: Lock held the entire time fetch_stories() spends on scoring. All concurrent callers freeze behind the lock.

- timestamp: 2026-04-27T00:07:00Z
  checked: run_text_story_cycle in __init__.py line 178
  found: agent_run.items_found = len(stories) is set immediately after fetch_stories() returns. Hung runs have items_found=0, proving fetch_stories() never returned.
  implication: Hang is definitively INSIDE fetch_stories(), not in the drafting loop.

- timestamp: 2026-04-27T00:30:00Z
  checked: coalesce pattern implementation — 5 concurrent callers test
  found: 5 concurrent callers → _do_fetch called exactly once, all receive same result, in-flight cleaned up, cache populated, subsequent calls hit fast path with 0 _do_fetch calls
  implication: Fix is correct. No long-held lock during Anthropic I/O possible.

## Resolution

root_cause: Sequential _score_relevance() for-loop (lines 1131-1138, pre-fix) ran entirely inside async with _CACHE_LOCK in fetch_stories(). With ~118 unique stories, one Anthropic call per story, at 2-30s per call, worst-case lock hold time was 59 minutes. All other fetch_stories()-using agents (sub_threads, sub_infographics, sub_quotes, subsequent sub_breaking_news) blocked on async with _CACHE_LOCK for the entire duration. No exceptions were raised — lock IS released when scoring completes, but "30s per call × 118 calls = total blocking time" is the actual bug. kro's 30s timeout reduced individual call ceiling but not the aggregate: 118 × 30s = 3,540s worst case.
fix: Implemented coalesce pattern (quick-260427-m51). Three changes: (1) Added _FETCH_IN_FLIGHT dict and _do_fetch() helper — all actual work (network I/O, Anthropic calls) moved to _do_fetch() which runs with NO lock held. (2) _CACHE_LOCK is now held ONLY for microsecond dict operations (cache check, Future registration/eviction, cache write). (3) Parallelised _score_relevance loop: replaced sequential for-loop with asyncio.gather over all stories, cutting worst-case scoring time from 118 × 30s = 3,540s to ~30s (single Anthropic timeout). Concurrent callers during an in-flight fetch await the same Future (coalesce) rather than queuing on the lock.
verification: 184 tests pass (183 existing + 1 new coalesce regression test). Ruff lint clean. Logic verified: we_own flag set inside _CACHE_LOCK ensuring atomic decision; result initialized to [] before try so finally block is always safe; Future resolved after cache write so waiters get consistent view.
files_changed: [scheduler/agents/content_agent.py, scheduler/tests/test_content_agent.py]
