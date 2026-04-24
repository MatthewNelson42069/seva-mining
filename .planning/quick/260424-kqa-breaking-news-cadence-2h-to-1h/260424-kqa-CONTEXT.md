# Quick Task 260424-kqa: Breaking News cadence 2h → 1h

**Gathered:** 2026-04-24
**Status:** Ready for execution (no planning ceremony — 1-integer diff)

## Task Boundary

User directive: *"Breaking news agent is doing a run every 30 minutes, change that to an hour"*

Observation vs code: production code sets `sub_breaking_news` to `IntervalTrigger(hours=2)` at `scheduler/worker.py:116` via `CONTENT_INTERVAL_AGENTS[0]`. There is NO 30-minute trigger anywhere in the scheduler — the only "30-min" signal is `misfire_grace_time=1800s` (which is a grace window for missed fires, NOT the interval). The most likely explanation for the user's "every 30 minutes" observation:

1. **Railway zero-downtime redeploys** — each restart resets `start_date = now + offset + 10s`, so on every redeploy `sub_breaking_news` (offset=0) fires ~10s later. If Railway deploys 4× in a day, breaking_news fires 4× plus its regular interval fires = more than expected.
2. **Dashboard timestamp misread** — agent_runs rows may include both `sub_breaking_news` and `sub_threads` (staggered +17min offset), and the user may be conflating the two streams visually.

Regardless, the ask is clear and the change is minimal: flip the interval from 2h to 1h.

## Locked Decisions

### D1 — Interval value
- `CONTENT_INTERVAL_AGENTS[0]` at `scheduler/worker.py:116` → change the last tuple element from `2` to `1`
- Test at `scheduler/tests/test_worker.py:534` → change `assert cadences["sub_breaking_news"] == 2` to `== 1`
- Narrative comments in `worker.py` that reference "every 2h" for sub_breaking_news → update to "every 1h" (lines 9, 108, 329)

### D2 — History
This is the SECOND time `sub_breaking_news` has been set to 1h:
- `m9k` (pre-vxg) tried 1h interval
- `vxg` (260422-vxg) reverted 1h → 2h as part of a cadence rebalance
- `kqa` (this task) reverts vxg — back to 1h
The header comment at `scheduler/agents/content/breaking_news.py:4` already notes "APScheduler cron (reverted from m9k's 1h experiment in quick-260422-vxg — 1h" — update this narrative reflectively to note the kqa revert.

### D3 — Out of scope
- Do NOT change any other cadence (threads stays 3h from j5i, quotes/infographics/gold_media/gold_history stay on their noon PT crons)
- Do NOT touch the Haiku gate prompt, the scoring curves (j5i landed), the SERPAPI_KEYWORDS list (htu + j5i landed)
- Do NOT investigate "why Railway restarts cause extra runs" — separate debug task if it persists post-deploy

## Validation
- `cd scheduler && uv run pytest -x` green (test_worker assertion update must pass)
- `cd scheduler && uv run ruff check .` clean
- `grep -n '"sub_breaking_news"' scheduler/worker.py` — tuple ends with `..., 0, 1)` (was `..., 0, 2)`)
- `grep -n '"sub_breaking_news": 1' scheduler/tests/test_worker.py` — match
- `git diff main` — only touches `scheduler/worker.py` + `scheduler/tests/test_worker.py` (+ .planning/ docs)

## Post-launch note
If user still sees "~30 minute" cadence after this deploys, the root cause is Railway restart frequency, not the interval setting. That's a separate investigation (Railway deploy cadence + APScheduler misfire_grace_time interaction).
