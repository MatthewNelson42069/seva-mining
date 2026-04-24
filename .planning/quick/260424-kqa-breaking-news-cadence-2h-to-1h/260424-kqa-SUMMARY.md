# Quick Task 260424-kqa: Breaking News cadence 2h → 1h — Summary

**Shipped:** 2026-04-24
**Commits:**
- T1 code: `ac90ee3` — `feat(scheduler): restore sub_breaking_news 1h cadence (kqa)`
- T2 docs (this commit): STATE.md row + SUMMARY.md + CONTEXT.md + PLAN.md

## What changed

| File | Change | Lines |
|------|--------|-------|
| `scheduler/worker.py:123` | `CONTENT_INTERVAL_AGENTS[0]` tuple `interval_hours` 2 → 1 | 1 |
| `scheduler/worker.py:32-40` | Module docstring: added kqa provenance line | +5 |
| `scheduler/worker.py:9` | "every 2h" → "every 1h" | 1 |
| `scheduler/worker.py:108-113` | narrative comment updated to record the kqa revert | ~5 |
| `scheduler/worker.py:329` | log-line updated `sub_breaking_news=2h` → `1h` | 1 |
| `scheduler/tests/test_worker.py:243-248` | `test_interval_agents_cadences` assertion `2` → `1` + docstring | ~2 |
| `scheduler/tests/test_worker.py:533-534` | removed stale "locked invariant" comment (2h was asserted here; now false) | -2 |
| `scheduler/agents/content/breaking_news.py:2-11` | module header rewritten to capture m9k→vxg→kqa history | ~8 |

Total diff: +25 insertions / -15 deletions across 3 files.

## Why

User observed *"Breaking news agent is doing a run every 30 minutes"* and asked to change it to an hour. The code was already at 2h — there is no 30-minute trigger anywhere in the scheduler. Most likely explanation:

**Railway zero-downtime redeploys** — each deploy restarts the scheduler worker. At `build_scheduler()` registration, `start_date = now + offset + 10s`. For `sub_breaking_news` (offset=0), every restart fires it ~10s later. Multiple deploys/day = extra fires beyond the interval cadence. The "every 30 min" observation likely reflects an unusually busy deploy period, not the interval literal.

We shipped what the user asked (1h) AND flagged the Railway-restart hypothesis for follow-up if the <1h cadence persists post-deploy.

## Why this doesn't reintroduce vxg's churn concern

vxg (260422-vxg) reverted m9k's 1h → 2h citing duplicate-story churn. Post-j5i (shipped earlier today, 2026-04-24):

1. `BREAKING_NEWS_MIN_SCORE = 6.5` — only top-of-top stories pass the gate (41% retention per j5i research Q5)
2. `max_count = 3` — even on busy news days, only 3 stories/run make it to the firehose
3. `sort_by = "score"` — composite-score sort guarantees the top 3 by relevance+recency+credibility
4. `fetch_stories()` 30-min TTL cache — the same ingestion cache is reused across adjacent runs within 30 min, so a 1h cadence doesn't double SerpAPI cost
5. `floored_by_min_score` telemetry — if the 6.5 floor is too aggressive, the counter surfaces it in `agent_run.notes`

These controls bound duplicate-story churn at 1h cadence in a way m9k's era couldn't.

## Validation

- `cd scheduler && uv run pytest -x` → 175 passed
- `cd scheduler && uv run ruff check .` → clean
- Preservation diff (excluding intended breaking_news.py narrative update): 0 bytes across `scheduler/agents/content/{quotes,threads,infographics,gold_media,gold_history}.py`, `content_agent.py`, `services/whatsapp.py`, `senior_agent.py`, `backend/`, `frontend/`, `alembic/`, `models/`

## Post-deploy monitoring

1. After Railway picks up `ac90ee3`, watch `agent_runs WHERE agent_name = 'sub_breaking_news'` — the `started_at` delta between consecutive rows should be ~60 min ± Railway restart jitter.
2. If the delta is consistently <60 min, the root cause is Railway restart frequency (redeploy + scheduler start_date reset). A follow-up debug task would investigate APScheduler's `coalesce=True` + `misfire_grace_time=1800` interaction with frequent restarts.
3. j5i's 41% breaking_news retention window still applies — keep monitoring `floored_by_min_score` counter on a 72h window.

## Follow-ups

- None in-scope for kqa. If Railway restart cadence is the real driver of <1h fires, that's a separate /gsd:debug session.
- Phase B (approve→auto-post to X) is the next user-requested task and comes after this ships.
