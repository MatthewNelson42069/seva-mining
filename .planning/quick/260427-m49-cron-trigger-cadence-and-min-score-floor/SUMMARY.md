# Quick Task 260427-m49 — CronTrigger cadence + min_score floor — SUMMARY

**Shipped:** 2026-04-27
**Branch:** `main` (no quick-task branch — small mechanical fix)

## Why

User: *"its running every few minutes now. It should run every hour instead. Fix that, and it is still not picking up any content"*

Two interlocking issues. Live Neon SQL on `sub_breaking_news`:

1. **Cadence "every few minutes" is real but not what it looks like.** The actual run interval was 60.0 min for most of the day — except the most recent runs at 22.7 min and 15.9 min apart. Root cause: `IntervalTrigger(hours=1, start_date=now+10s)` fires the job ~10s after every Railway restart. Each redeploy (the kro fix push counted as one) re-fires `sub_breaking_news` immediately because `offset=0`. With deploy churn, the user perceives "every few minutes." Flagged as a follow-up in kqa's SUMMARY but not actually fixed there.

2. **Score floor too aggressive.** Last 24h, 10 completed runs: drafted=58, **floored_by_min_score=40 (69%)**, queued=13. j5i's own SUMMARY says: *"if >70% of compliance-passed stories floor across a 24h window, drop to 6.0"*. We're sitting at the boundary, and the user has explicitly said "still not picking up content" — the 6.5 floor is filtering out genuinely-fine stories.

## Fix

Two surgical changes:

### A. CronTrigger for the two interval sub-agents

`scheduler/worker.py`:
- **Retired `CONTENT_INTERVAL_AGENTS` entirely.** All 6 sub-agents now register through `CONTENT_CRON_AGENTS` with the existing `(job_id, run_fn, name, lock_id, cron_kwargs: dict)` tuple shape.
- `sub_breaking_news` → `{"minute": 0}` — fires at HH:00 UTC every hour.
- `sub_threads` → `{"hour": "*/3", "minute": 17}` — fires at 00:17, 03:17, 06:17, 09:17, 12:17, 15:17, 18:17, 21:17 UTC. The `:17` minute offset preserves the staggering vs `sub_breaking_news`'s `:00` fire-time that the pre-m49 IntervalTrigger `offset=17` expressed.
- Removed the `IntervalTrigger` import and the `now = datetime.now(...) ... start_date = now + timedelta(...)` registration loop.
- `build_scheduler` is now a single loop over `CONTENT_CRON_AGENTS`.

**Why CronTrigger is restart-immune:** `IntervalTrigger` fires at `start_date` and every interval thereafter. We were setting `start_date = scheduler_start_time + offset + 10s`, so each Railway redeploy re-anchored `start_date` to ~10s after process start — the job fired immediately after every restart. `CronTrigger` fires at clock-aligned moments (HH:00 UTC, regardless of when the process booted), so restarts cannot cause spurious runs.

Verified locally: `CronTrigger(minute=0, timezone='UTC').get_next_fire_time(...)` after a hypothetical 22:47 restart returns `23:00:00+00:00` — clean 13-min wait, no 10s-after-startup fire.

### B. BREAKING_NEWS_MIN_SCORE 6.5 → 6.0

`scheduler/agents/content/breaking_news.py:42`:
```python
BREAKING_NEWS_MIN_SCORE: float = 6.0
```

Per j5i's own observability threshold ("drop to 6.0 if >70% floors") and the live 69% rate. Projected retention from j5i Q5: ~62% at 6.0 vs ~41% at 6.5 — should significantly increase queue throughput.

`THREADS_MIN_SCORE` stays at 6.5 (user only complained about breaking_news; threads cadence and floor were not part of the report).

## Tests

| Test | Change |
|------|--------|
| `test_interval_agents_cadences` | DELETED (no more interval agents) |
| `test_sub_threads_interval_is_three_hours` | DELETED (replaced by `test_threads_is_every_three_hours_cron`) |
| `test_sub_agent_staggering` | DELETED (no more `offset` field on the tuple shape) |
| `test_sub_agents_total_six` | UPDATED: `len(CONTENT_CRON_AGENTS) == 6` (was 2 interval + 4 cron) |
| `test_sub_agent_lock_ids` | UPDATED: iterates only over `CONTENT_CRON_AGENTS` |
| `test_cron_agents_count_four` | RENAMED to `test_cron_agents_count_six` + added `sub_breaking_news` + `sub_threads` to expected set |
| `test_cron_agents_use_dict_shape` | UPDATED: noon-PT assertion gated to the 4 cron agents that actually fire at noon (BN + Threads use different shapes) |
| **NEW** `test_breaking_news_is_hourly_cron` | Asserts `cron_kwargs == {"minute": 0}` |
| **NEW** `test_threads_is_every_three_hours_cron` | Asserts `cron_kwargs == {"hour": "*/3", "minute": 17}` |
| `test_breaking_news_min_score_constant` | UPDATED: 6.5 → 6.0 |
| `test_breaking_news_passes_selection_kwargs` | UPDATED: 6.5 → 6.0 |

Test totals: 184 → 183 (net -3 deleted + 2 added in test_worker.py; test_breaking_news.py count unchanged).

## What this does NOT touch

- `THREADS_MIN_SCORE` (kept at 6.5 — user did not flag threads as floor-starved)
- `test_content_wrapper.py` floor-mechanism tests that pass `min_score=6.5` as a synthetic input — those test the floor mechanism with a specific test value, not the production constant
- `coalesce`/`max_instances`/`misfire_grace_time` job defaults — unchanged
- `reconcile_stale_runs` — unchanged
- The 4 cron sub-agents (quotes/infographics/gold_media/gold_history) — fire times unchanged

## Validation

- `cd scheduler && uv run pytest -x` → **183 passed**, 1.1s
- `cd scheduler && uv run ruff check .` → clean
- Functional smoke test: instantiated `CronTrigger(minute=0)` and `CronTrigger(hour='*/3', minute=17)` directly, confirmed fire-time sequences are clock-aligned and do not key off process start time.

## Operational impact (after Railway picks this up)

- The 8 stuck `running` rows from the kro deadlock will be swept by `reconcile_stale_runs` on the m49 redeploy startup.
- New worker registers all 6 sub-agents on CronTrigger. No more "10s after restart" fires.
- `sub_breaking_news` next fire after deploy lands: the next HH:00 UTC mark.
- `sub_threads` next fire after deploy lands: the next `HH:17` UTC mark where `HH ∈ {0, 3, 6, 9, 12, 15, 18, 21}`.
- With `BREAKING_NEWS_MIN_SCORE=6.0`, expect queue throughput ~50% higher than the recent 69%-floored baseline. If the new rate is too loose (e.g. >80% retention with low-quality stories surfacing), nudge back to 6.25 or 6.5 — single-line tunable.

## Follow-ups (not in this task)

- Consider lowering `THREADS_MIN_SCORE` if the same observability pattern shows up there (currently 50% retention per j5i Q5 — within the band, leave alone for now).
- The `_score_relevance` sequential loop is still the deadlock-amplification surface even with kro's 30s timeout — moving it to `asyncio.gather()` would cut worst-case fetch_stories runtime from 60 min to 30s. Larger refactor; deferred.
