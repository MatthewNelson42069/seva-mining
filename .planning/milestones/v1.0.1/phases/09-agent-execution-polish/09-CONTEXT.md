# Phase 9: Agent Execution Polish - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Make all remaining hardcoded agent configuration DB-driven so values can be tuned from the Settings page without a code deploy. Wire the agent schedule intervals (already editable in the Schedule tab UI) to the APScheduler jobs in worker.py. This phase does NOT add new agent capabilities, new UI pages, or new agents.

</domain>

<decisions>
## Implementation Decisions

### Engagement Gate Thresholds → DB-driven (EXEC-02)

Move engagement gate thresholds out of code constants into DB config keys, readable by each agent at the start of every run:

**Twitter Agent:**
- `twitter_min_likes_general` = 500 (current hardcoded: non-watchlist gate)
- `twitter_min_views_general` = 40000
- `twitter_min_likes_watchlist` = 50 (current hardcoded: watchlist gate)
- `twitter_min_views_watchlist` = 5000

**Instagram Agent:**
- `instagram_min_likes` = 200 (current hardcoded: engagement gate)
- `instagram_max_post_age_hours` = 8 (current hardcoded: age window)

These values should be surfaced on the Settings → Scoring tab alongside the existing content agent weights.

### Recency Decay Breakpoints → Stay Hardcoded

Twitter recency decay breakpoints (full score <1h, 50% at 4h, expires at 6h) remain as code constants. Too granular to be worth live-tuning; if they ever need changing, a deploy is fine.

### Schedule Intervals → DB-driven, Apply on Next Restart

Move APScheduler job intervals from hardcoded values in `worker.py` to DB config keys:
- `twitter_interval_hours` = 2
- `instagram_interval_hours` = 4
- `content_agent_schedule_hour` = 6 (cron hour for 6am daily)
- `expiry_sweep_interval_minutes` = 30
- `morning_digest_hour` = 8 (cron hour for 8am daily)

`worker.py` reads these from DB at startup, then sets up APScheduler jobs. Schedule tab already says "changes take effect on next worker restart" — this behaviour is correct and expected.

### Seed Scripts

Each agent that gains new config keys needs a seed script update (or new seed entries) so fresh deployments have sane defaults pre-populated.

### Claude's Discretion
- Where in `_run_pipeline` each agent reads new config keys (start of run, before pipeline logic)
- Error handling if a config key is missing at startup (fall back to hardcoded default, log warning)
- Whether to consolidate seed entries into a single Phase 9 seed script or extend existing per-agent seeds

</decisions>

<specifics>
## Specific Ideas

- The Schedule tab already reads any config key containing "schedule" or "interval" — naming the keys with those substrings means the tab picks them up automatically with no UI changes needed.
- The Scoring tab reads all config keys — new engagement gate keys will appear there automatically too (the tab is generic, not filtered by key name).

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Agent config patterns (existing DB-driven examples to replicate)
- `scheduler/agents/content_agent.py` §_run_pipeline — shows the `_get_config(session, key, default)` pattern used to read config at runtime
- `scheduler/agents/twitter_agent.py` §_get_config, §_set_config — Twitter's existing config read/write helpers
- `scheduler/agents/instagram_agent.py` §_get_config — Instagram's existing config read helper

### Hardcoded values being migrated
- `scheduler/agents/twitter_agent.py` §passes_engagement_gate (lines ~144-171) — thresholds to move to DB
- `scheduler/agents/instagram_agent.py` §passes_engagement_gate (lines ~59-70) — threshold to move to DB
- `scheduler/worker.py` §build_scheduler (lines ~179-215) — hardcoded intervals to move to DB

### Settings UI (already built — no changes needed)
- `frontend/src/components/settings/ScheduleTab.tsx` — reads keys containing "schedule" or "interval"
- `frontend/src/components/settings/ScoringTab.tsx` — reads all config keys generically

### Requirements
- `.planning/REQUIREMENTS.md` §EXEC-02 — "Agents read scoring settings from database at start of each run (no cached config)"

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_get_config(session, key, default)` pattern: exists in all three agents — new config reads follow the exact same pattern
- `seed_*.py` scripts per agent: each has an existing seed script to extend with new config keys

### Established Patterns
- Config reads happen at the top of `_run_pipeline` (Content Agent pattern) — Twitter and Instagram should match
- Default values are always passed as strings; callers cast (`int()`, `float()`)
- Config keys use snake_case with agent prefix: `twitter_*`, `instagram_*`, `content_*`

### Integration Points
- `scheduler/worker.py` `build_scheduler()` function — where schedule intervals are read and APScheduler jobs are registered
- `scheduler/seed_*.py` — new config keys need default values seeded here
- Settings → Scoring tab: picks up new keys automatically (no UI changes)
- Settings → Schedule tab: picks up new keys containing "schedule" or "interval" automatically (no UI changes)

</code_context>

<deferred>
## Deferred Ideas

- Live schedule rescheduling without restart — would require APScheduler job modification at runtime; complexity not justified for v1
- Content Agent RSS feeds and SerpAPI keywords as DB-driven config — user wants to discuss this separately; may become a backlog item or Phase 9.1

</deferred>

---

*Phase: 09-agent-execution-polish*
*Context gathered: 2026-04-03*
