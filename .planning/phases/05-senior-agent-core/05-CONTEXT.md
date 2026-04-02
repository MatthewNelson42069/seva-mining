# Phase 5: Senior Agent Core - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the Senior Agent Core: the layer that sits between the sub-agents (Twitter, Instagram, Content) and the operator's approval queue. It enforces the 15-item hard cap with priority tiebreaking, deduplicates same-story items across platforms and links them as "related," runs the 30-minute expiry sweep (Twitter 6h, Instagram 12h), assembles and dispatches the daily 8am WhatsApp morning digest, and fires WhatsApp alerts for breaking stories and approaching expirations.

This phase does NOT include: Instagram Agent, Content Agent, dashboard views/settings, or any agent configuration from the UI. Those are Phases 6–9.

The Senior Agent is not a single scheduled job — it spans two APScheduler jobs already registered in `worker.py` (`expiry_sweep` at 30-minute intervals and `morning_digest` at 8am daily) plus inline queue management called when sub-agents write DraftItems.

</domain>

<decisions>
## Implementation Decisions

### Story Deduplication (SENR-02)

**Method: text overlap check** — fast, zero API cost, no Claude call required.

How it works:
- When a new DraftItem is written to the DB, extract a set of "fingerprint tokens" from `source_text` and `rationale`: lowercase, strip punctuation, remove stopwords, keep meaningful terms (company names, gold price figures, event names, numbers)
- Compare against all other `pending` DraftItems created in the last 24 hours
- If token overlap ≥ 40% (Jaccard similarity), treat as same story → set `related_id` on the newer item pointing to the older item
- Result: both cards remain in the queue as separate platform cards; they are visually linked on the dashboard via `related_id`
- Neither card is dropped — SENR-02 explicitly requires both surface as separate cards

The 40% threshold and 24-hour lookback window are configurable via the `config` table.

### Breaking News Alert Threshold (WHAT-02)

**Score ≥ 8.5/10 triggers an immediate WhatsApp breaking news alert.**

Behavior:
- Fired inside the same function that enforces the queue cap — after a new DraftItem is committed, if `score >= 8.5`, send the `breaking_news` WhatsApp template immediately
- Template variables: `{{1}}` = item rationale headline (first sentence), `{{2}}` = source_account, `{{3}}` = score rounded to 1 decimal, `{{4}}` = dashboard URL
- Only fires once per item (flag in `config` table or check `draft_items` created_at to avoid double-fire on restart)
- Threshold stored as `senior_breaking_news_threshold` in `config` table (default: `"8.5"`) — operator can adjust

### Expiry Alert Timing (WHAT-03)

**Fire once when a pending item with score ≥ 7.0 has ≤ 1 hour until expiry.**

Behavior:
- Detected by the 30-minute expiry sweep job
- Query: `SELECT * FROM draft_items WHERE status='pending' AND score >= 7.0 AND expires_at BETWEEN now() AND now() + interval '1 hour'`
- Send `expiry_alert` WhatsApp template: `{{1}}` = platform, `{{2}}` = rationale headline (first sentence), `{{3}}` = minutes remaining, `{{4}}` = dashboard URL
- Deduplication: track sent alerts so each item only triggers one alert (use a `alerted_expiry_at` column on `draft_items`, or a config key `expiry_alert_sent:{item_id}`)
- Thresholds stored in `config` table: `senior_expiry_alert_score_threshold` (default: `"7.0"`) and `senior_expiry_alert_minutes_before` (default: `"60"`)

### Queue Cap Enforcement (SENR-04)

Hard cap of 15 pending items. Enforced inline when any sub-agent writes a new DraftItem.

Logic:
1. Count `pending` items in `draft_items`
2. If count < 15: accept new item normally
3. If count == 15 and new item score > lowest pending score: delete the lowest-scoring pending item, insert the new one
4. If count == 15 and new item score ≤ lowest pending score: discard the new item (log to AgentRun.notes)
5. Tiebreaking: when two items share the lowest score, prefer to keep the one with the later `expires_at` (more time remaining)

Cap limit stored as `senior_queue_cap` in `config` table (default: `"15"`).

### Priority Ordering (SENR-03)

Queue prioritization for display on dashboard (sort order, not enforcement):
1. Twitter items with `expires_at` within 2 hours (time-sensitive first)
2. Content Agent items marked as breaking news (high score + content platform)
3. Instagram items
4. Evergreen (Content Agent items with low urgency flag)

The `urgency` column on `DraftItem` is already used by the Twitter Agent. Senior Agent reads this + `expires_at` + `platform` to set display priority. No new columns needed.

### Auto-Expiry Sweep (SENR-05, SENR-09)

The `expiry_sweep` job runs every 30 minutes. It:
1. Marks expired: `UPDATE draft_items SET status='expired', updated_at=now() WHERE status='pending' AND expires_at < now()`
2. Checks for expiry alerts (see above)
3. Logs run to `agent_runs` with `agent_name='expiry_sweep'`

Expiry windows (already set by sub-agents when writing DraftItems):
- Twitter: `expires_at = created_at + 6 hours` (set by Twitter Agent)
- Instagram: `expires_at = created_at + 12 hours` (set by Instagram Agent, Phase 6)
- Content: no expiry (evergreen — `expires_at = NULL`)

### Morning Digest Assembly (SENR-06, SENR-07)

The `morning_digest` job runs daily at 8:00 AM. It:
1. Queries yesterday's data: approved count, rejected count, expired count
2. Queries current queue snapshot: count by platform
3. Selects top 5 stories from items created/updated yesterday (by score, across platforms)
4. Selects single highest-scoring currently-pending item as priority alert
5. Writes a `DailyDigest` record to DB
6. Sends `morning_digest` WhatsApp template with 7 variables:
   - `{{1}}` = today's date (YYYY-MM-DD)
   - `{{2}}` = top story headlines joined by "; " (truncated to fit)
   - `{{3}}` = total pending queue count
   - `{{4}}` = yesterday's approved count
   - `{{5}}` = yesterday's rejected count
   - `{{6}}` = yesterday's expired count
   - `{{7}}` = dashboard URL (from `config` table key `dashboard_url`, default: `"https://app.sevamining.com"`)

Note: SENR-07 mentions "@sevamining scraped surface metrics" — this requires Twitter API access to @sevamining's own account. Since X API is not yet live and there is no `sevamining_metrics` column in `DailyDigest`, this section is deferred to Phase 8 (dashboard view) or when X API is configured.

### WhatsApp Service in Scheduler

The WhatsApp service (`send_whatsapp_template`) lives in `backend/app/services/whatsapp.py`. The scheduler worker is a separate process with no access to the backend package. Phase 5 creates `scheduler/services/whatsapp.py` — a direct mirror of the backend service using the same SIDs, same async pattern (`asyncio.to_thread`), same retry-once behavior.

Template SIDs (already registered):
- `morning_digest`: `HX930c2171b211acdea4d5fa0a12d6c0e0`
- `breaking_news`: `HXc5bcef9a42a18e9071acd1d6fb0fac39`
- `expiry_alert`: `HX45fd40f45d91e2ea54abd2298dd8bc41`

### Approval/Rejection Logging (SENR-08)

Approvals and rejections are already captured on `DraftItem`:
- `status` ∈ {approved, edited_approved, rejected}
- `rejection_reason` text field (set by operator via dashboard)
- `decided_at` timestamp

The Senior Agent reads these fields to compute digest stats. No new logging schema needed. "Reason tags" in the spec refers to `rejection_reason` free-text — no structured tag taxonomy is required for Phase 5.

### Claude's Discretion

- Exact Jaccard similarity threshold (suggested: 0.40) and token extraction logic
- Stopword list for fingerprint token extraction
- SQL query structure for the expiry sweep
- Config key names and default values (follow existing `twitter_*` naming pattern)
- Error handling for WhatsApp send failures in the scheduler (match backend pattern: log + retry once)
- `DailyDigest` JSONB field structure for `top_stories`, `queue_snapshot`, etc.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Specification
- `.planning/REQUIREMENTS.md` §Senior Agent — SENR-01 through SENR-09
- `.planning/REQUIREMENTS.md` §WhatsApp Notifications — WHAT-01 through WHAT-05
- `.planning/ROADMAP.md` §Phase 5 — Success criteria and dependency context

### Existing Models (all deployed to Neon)
- `backend/app/models/draft_item.py` — DraftItem schema (status enum, related_id FK, score, expires_at, urgency, platform)
- `backend/app/models/daily_digest.py` — DailyDigest schema (top_stories, queue_snapshot, yesterday_* JSONB columns, whatsapp_sent_at)
- `backend/app/models/agent_run.py` — AgentRun schema for run logging
- `backend/app/models/config.py` — Config key-value store for thresholds
- `scheduler/models/` — Scheduler-local mirrors of all the above

### Existing Services
- `backend/app/services/whatsapp.py` — Template SIDs, async send pattern, retry-once logic (MIRROR this in scheduler)

### Existing Scheduler Patterns
- `scheduler/worker.py` — `expiry_sweep` (lock ID 1004) and `morning_digest` (lock ID 1005) job slots already registered; `_make_job` pattern for wiring real agents
- `scheduler/agents/twitter_agent.py` — Full example of agent structure: `AsyncSessionLocal`, `AgentRun` logging, error handling, `AsyncAnthropic` usage

### WhatsApp Template Variable Maps
- `.planning/phases/01-infrastructure-and-foundation/01-01-PLAN.md` — Exact template body text and variable slot definitions for all 3 templates

### Stack Decisions
- `CLAUDE.md` §Technology Stack — APScheduler 3.11.2 AsyncIOScheduler, `asyncio.to_thread` for sync Twilio SDK

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DraftItem.related_id` — UUID FK to self, already in schema and indexed. Set on newer item pointing to older item when deduplication detects same story.
- `DraftItem.status = 'expired'` — Already a valid enum value. Expiry sweep just runs an UPDATE.
- `DraftItem.expires_at` — Already indexed (`ix_draft_items_expires_at`). Expiry query is fast.
- `DraftItem.score` — Already set by Twitter Agent. Queue cap displacement logic is a straightforward SELECT + compare.
- `DailyDigest` model — All fields match SENR-07 requirements. `whatsapp_sent_at` tracks whether dispatch succeeded.
- `Config` model — Key-value store for all thresholds. Already in DB via migration 0003.

### Established Patterns
- Scheduler agent structure: `TwitterAgent.run()` pattern in `scheduler/agents/twitter_agent.py` — use as template for `SeniorAgent`
- Worker wiring: `_make_job(job_name, engine)` in `worker.py` — Phase 5 replaces `expiry_sweep` and `morning_digest` placeholders with real Senior Agent methods
- DB sessions: `AsyncSessionLocal` from `scheduler/database.py`
- Error isolation: catch all exceptions in job body, log to `AgentRun.errors`, set `status='failed'`, never re-raise

### Integration Points
- `expiry_sweep` job → wire to `SeniorAgent.run_expiry_sweep()`
- `morning_digest` job → wire to `SeniorAgent.run_morning_digest()`
- Queue cap + deduplication → called by sub-agents after writing DraftItem, OR implemented as a `SeniorAgent.process_new_item(item_id)` function called by Twitter Agent (and future agents)
- No direct inter-agent calls — all communication via PostgreSQL DB

</code_context>

<specifics>
## Specific Decisions

- Text overlap (Jaccard similarity ≥ 0.40) for story deduplication — no Claude call, no API cost
- Score ≥ 8.5 triggers immediate breaking news WhatsApp alert (configurable via `senior_breaking_news_threshold`)
- Expiry alert fires at ≤ 1 hour before expiry for items with score ≥ 7.0 (configurable thresholds)
- @sevamining own metrics deferred — no field in DailyDigest, not in scope for Phase 5

</specifics>

<deferred>
## Deferred Ideas

- @sevamining scraped surface metrics in morning digest (SENR-07 partial) — no DailyDigest column for this; requires X API to be live; defer to Phase 8 or post-launch
- Structured rejection reason taxonomy (tags vs free text) — free text `rejection_reason` is sufficient for Phase 5 digest stats; structured tags deferred to v1.x learning loop (LERN-01)

</deferred>

---
*Phase: 05-senior-agent-core*
*Context gathered: 2026-04-02*
