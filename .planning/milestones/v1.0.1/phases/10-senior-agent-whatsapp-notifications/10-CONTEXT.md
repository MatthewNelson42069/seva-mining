# Phase 10: Senior Agent WhatsApp Notifications - Context

**Gathered:** 2026-04-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the Senior Agent's WhatsApp notification system to production using the Twilio WhatsApp Sandbox. Three notification types are needed: morning digest (7am PST), new item alerts (instantly when any agent creates draft items), and removal of the expiry sweep job. The WhatsApp service must be rewritten from template-SID-based to free-form sandbox messages.

This phase does NOT add new agent capabilities, new dashboard pages, or new queue logic. It only wires notifications and adjusts the scheduler.

</domain>

<decisions>
## Implementation Decisions

### Morning Digest Timing
- Runs at **7am PST = 15:00 UTC** daily
- Update `morning_digest_schedule_hour` DB config default from `"8"` to `"15"`
- The cron job in worker.py reads this from DB — updating the seed default and the DB value is sufficient, no hardcoded change needed

### New Item Notifications
- Fire a WhatsApp message **every time** any agent (Twitter, Instagram, Content) creates one or more new DraftItems
- Message format: plain text, names the agent and the count — e.g. "Twitter Agent found 3 new items for your review 👀"
- Send ONLY when items were actually created (count > 0) — do not fire on runs with zero new items
- The notification fires at the END of each agent's run, after items are committed to DB
- This replaces the breaking_news/engagement alert system entirely for V1 — simple is better

### Expiry Sweep Removal
- Remove `expiry_sweep` from `JOB_LOCK_IDS` in worker.py
- Remove the `expiry_sweep` APScheduler job registration from `build_scheduler()`
- Keep `run_expiry_sweep()` in senior_agent.py (don't delete it — may be re-enabled later)
- Remove `expiry_sweep_interval_minutes` from the schedule config seed

### WhatsApp Service Rewrite
- Switch from `content_sid` (template SIDs) to `body` (free-form text) in the Twilio messages.create() call
- Twilio sandbox (+14155238886) supports free-form messages when recipient has opted in via "join government-accident"
- Keep `send_whatsapp_template()` function signature for backward compatibility but internally send free-form body
- OR rename to `send_whatsapp_message(message: str)` — simpler, cleaner. Use this.
- Remove `TEMPLATE_SIDS` dict entirely — not needed for sandbox
- Graceful failure: if Twilio credentials are missing/None, log a warning and skip (don't crash agents)

### Twilio Credentials
- `TWILIO_ACCOUNT_SID` — from Railway scheduler env vars
- `TWILIO_AUTH_TOKEN` — from Railway scheduler env vars
- `TWILIO_WHATSAPP_FROM` = `whatsapp:+14155238886` (Twilio sandbox number)
- `DIGEST_WHATSAPP_TO` = operator's WhatsApp number in `whatsapp:+1XXXXXXXXXX` format
- All already Optional in scheduler/config.py — graceful skip if absent

### Notification Hook Location
- Twitter Agent: add notification call in `run()` after DraftItems are committed, pass count of new items
- Content Agent: add notification call in `run()` after bundle/items committed
- Instagram Agent: add notification call in `run()` after DraftItems committed
- Notification function lives in `services/whatsapp.py` — agents import it directly
- Use `asyncio.create_task()` or plain `await` — await is fine, Twilio call is fast

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### WhatsApp Service
- `scheduler/services/whatsapp.py` — Current template-based implementation to rewrite
- `scheduler/config.py` — Optional Twilio fields (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, DIGEST_WHATSAPP_TO)

### Scheduler & Jobs
- `scheduler/worker.py` — JOB_LOCK_IDS dict, build_scheduler(), _read_schedule_config(), expiry_sweep job to remove
- `scheduler/seed_twitter_data.py` — Config defaults including morning_digest_schedule_hour and expiry_sweep_interval_minutes

### Agents to Wire
- `scheduler/agents/twitter_agent.py` — run() method, end of execution, DraftItem creation pattern
- `scheduler/agents/content_agent.py` — run() method, end of execution
- `scheduler/agents/instagram_agent.py` — run() method, end of execution
- `scheduler/agents/senior_agent.py` — run_morning_digest(), run_expiry_sweep() (to keep but unschedule)

</canonical_refs>

<specifics>
## Specific Ideas

- Morning digest message should be concise — queue count, top item score, brief summary. Not a wall of text.
- New item notification: "🐦 Twitter Agent — 3 new items ready for review" style formatting
- Sandbox join code: `join government-accident` to `+1 415 523 8886`
- Operator's number will be set via `DIGEST_WHATSAPP_TO` env var in Railway

</specifics>

<deferred>
## Deferred Ideas

- Upgrade from Twilio sandbox to production approved templates (Meta approval required — do later once sandbox is working)
- Expiry sweep re-enablement — kept in code but not scheduled
- Per-agent opt-in/opt-out notification preferences from Settings page

</deferred>

---

*Phase: 10-senior-agent-whatsapp-notifications*
*Context gathered: 2026-04-07*
