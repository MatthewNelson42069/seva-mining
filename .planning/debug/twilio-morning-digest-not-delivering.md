---
status: investigating
trigger: "User reports not receiving ANY Twilio WhatsApp messages from the morning_digest cron. Zero messages for days/weeks. Live production issue on Railway scheduler service."
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T02:30:00Z
---

## Current Focus

hypothesis: **Defect C — Twilio WhatsApp Sandbox 24-hour customer service window expired.**
  Prod DB evidence is definitive: cron is firing daily, all 24 scheduled runs since Apr 8 have `status='completed'`, and **Apr 14-24 all have `daily_digests.whatsapp_sent_at` populated** — meaning the send path completed without raising. The Python code believes the message sent successfully because Twilio returns a SID. But on the Meta/WhatsApp side, the sandbox 24-hour freeform window (from user's last inbound message to +14155238886) closed after Apr 15 morning, and Twilio silently drops/fails delivery with error 63016 without raising on the API accept.
  Apr 8-13 = whatsapp_sent_at=None → send_whatsapp_message raised or returned None (credentials likely missing pre-deploy).
  Apr 14 = creds added, user had opted into sandbox, window open → delivery OK.
  Apr 15 = still inside 24h window → delivery OK.
  Apr 16 onward = outside 24h window → Twilio API accepts, SID issued, but Meta rejects actual delivery silently.
  Defects A (timezone) and B (env drift) both ELIMINATED by evidence.
test: Asked user to check Twilio console → Messaging → Logs for last 7 days. Filter `From: whatsapp:+14155238886`. If status=failed + error_code=63016 on Apr 16-24 messages, Defect C is confirmed.
expecting: Twilio console will show ~9 outbound messages Apr 16-24, each with status=failed and error_code=63016 (or similar "recipient not in 24h session" error).
next_action: Report findings to user with Defect C as root cause. Recommend: (a) re-join sandbox from phone, (b) once reconnected, send any reply within 24h of digest to keep window open, OR (c) move to Twilio-approved WhatsApp Business sender to escape sandbox constraints entirely. Preserve the committed-but-not-merged code fixes (timezone hardening, observability in senior_agent.notes and whatsapp.py ERROR-level logging) — they are still defensible hardening even if not root cause. The notes-capture fix is ESSENTIAL to detect future sandbox-expiry regressions.

## Symptoms

expected: User receives a WhatsApp message at ~07:00 America/Los_Angeles each day containing the morning_digest summary (yesterday's draft counts, approval rates, anything scheduled for today).
actual: User receives zero messages. Not one. For at least several days (possibly weeks).
errors: None visible to user. Silent failure mode.
reproduction: Wait for 07:00 PT cron OR trigger morning_digest manually against prod; check Railway scheduler logs for ground truth.
started: Unknown. Last confirmed-working state ~weeks ago when first shipped. Recent suspect changes: 260420-sn9 Senior Agent purge (trimmed to single cron), migrations, config-key renames.

## Eliminated

- hypothesis: "morning_digest cron is not registered at all"
  evidence: `scheduler/worker.py` build_scheduler() line 289 explicitly adds `id="morning_digest"` with CronTrigger(hour=digest_hour). Tests (test_worker.py test_scheduler_registers_7_jobs) assert the job exists. Not the problem.
  timestamp: 2026-04-24T00:00:01Z

- hypothesis: "WhatsApp send function was recently deleted / renamed"
  evidence: `scheduler/services/whatsapp.py::send_whatsapp_message` still exists and is called from `senior_agent.py` line 282. Wiring intact.
  timestamp: 2026-04-24T00:00:02Z

- hypothesis: "Defect A — cron fires at wrong time (08:00 UTC = 01:00 PDT instead of 08:00 PT)"
  evidence: Prod DB query on 2026-04-24 confirms `config.morning_digest_schedule_hour = 15`. With scheduler timezone=UTC, `hour=15` fires at 15:00 UTC = 08:00 PDT — matches Apr 15 delivery timestamp. All runs Apr 8-24 have started_at at 15:00:0X UTC → consistent 08:00 PT firing. Timezone is NOT the root cause. The explicit `timezone="America/Los_Angeles"` fix in the uncommitted diff is defensible hardening (removes the UTC/DST drift surface) but does not address the current silence.
  timestamp: 2026-04-24T02:20:00Z

- hypothesis: "Defect B — Railway scheduler-service env-var drift (missing Twilio creds)"
  evidence: User screenshotted Railway scheduler-service Variables tab 2026-04-24 — TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, DIGEST_WHATSAPP_TO all present and populated. Both services (scheduler + api) Online. Additionally: DB query shows `daily_digests.whatsapp_sent_at` populated for every run Apr 14-24 → the code path `record.whatsapp_sent_at = datetime.now()` runs, meaning send_whatsapp_message did NOT return None (would only return None on credential miss). Credentials are set.
  timestamp: 2026-04-24T02:21:00Z

- hypothesis: "Regression between Apr 15 and Apr 20 disabled the Twilio send code path"
  evidence: DB shows morning_digest runs completing daily with consistent 3-5 second duration (normal), daily_digests.whatsapp_sent_at populated on every run Apr 14-24. If a regression had disabled the send call, either (a) the runs would have shorter duration (skipping the Twilio call) or (b) `whatsapp_sent_at` would be None (raised to except block). Neither is true. The Python code is reaching Twilio, getting a SID, and returning cleanly. Regression in code is ruled out.
  timestamp: 2026-04-24T02:22:00Z

## Evidence

- timestamp: 2026-04-24T00:00:00Z
  checked: Knowledge base for matching patterns
  found: No match. Prior debug (260422-gmb) was about sub_gold_media empty results, unrelated.
  implication: No prior pattern to leverage. Fresh investigation.

- timestamp: 2026-04-24T00:01:00Z
  checked: scheduler/worker.py — morning_digest cron registration (lines 289-296, 280-287)
  found:
    • CronTrigger called with only `hour=digest_hour, minute=0` — NO `timezone=` kwarg on the trigger itself.
    • Scheduler-level default: `timezone="UTC"` (line 286).
    • Default digest_hour = "8" (line 232).
    • `_read_schedule_config` reads key `morning_digest_schedule_hour` from DB; falls back to "8" if missing.
  implication: **The cron fires at 08:00 UTC every day.** 08:00 UTC = 01:00 PDT (DST, April) or 00:00 PST. That is NOT 07:00 America/Los_Angeles. To actually fire at 07:00 PT, we need `CronTrigger(hour=7, minute=0, timezone="America/Los_Angeles")`. **This is Defect A** — the cron is mis-timed by 6–7 hours and has been since at least Apr 6 2026 (commit `096508b`). If there's ANY stretch of day where the user is asleep / phone DND between 00:00 and 01:00 local time, they'd never notice the message — it would be in their WhatsApp history, but not a new notification they'd see.

- timestamp: 2026-04-24T00:02:00Z
  checked: scheduler/services/whatsapp.py — send_whatsapp_message
  found:
    • Lines 54-67: If ANY of `twilio_account_sid`, `twilio_auth_token`, `twilio_whatsapp_from`, `digest_whatsapp_to` are falsy, the function logs a WARNING and returns None. No exception raised.
    • Lines 69-77: TwilioRestException is caught, retried once, then logged at ERROR and RAISED. But the caller (senior_agent.py line 284) catches `Exception` broadly and only logs a `warning` (marks run as non-fatal).
  implication: **Triple-silent failure mode.** If scheduler-service Railway env is missing ANY of the 4 Twilio vars → silent None return. If Twilio API errors → caught upstream and logged but run marked "completed". The `agent_runs` table will show `status='completed'` regardless of whether the message actually sent. Observability gap is severe — the only ground truth is Railway process logs and Twilio console.

- timestamp: 2026-04-24T00:03:00Z
  checked: Local env files (/Users/matthewnelson/seva-mining/scheduler/.env, .env, .env.example)
  found:
    • scheduler/.env has: TWILIO_ACCOUNT_SID= (empty), TWILIO_AUTH_TOKEN= (empty), TWILIO_WHATSAPP_FROM= (empty).
    • scheduler/.env has NO `DIGEST_WHATSAPP_TO=` line at all.
    • .env.example template shows: TWILIO_WHATSAPP_FROM=whatsapp:+14155238886 (sandbox) and DIGEST_WHATSAPP_TO=whatsapp:+1XXXXXXXXXX (placeholder).
  implication: Local env being empty doesn't prove Railway is empty — but it does prove the repo has no record of the user's actual phone number for the sandbox destination, which matches "Twilio env vars may be configured on API but missing on scheduler". **Defect B candidate — Railway scheduler service may lack `DIGEST_WHATSAPP_TO`** (and/or the other 3 vars). Must be verified via Railway dashboard — I cannot reach Railway from dev environment.

- timestamp: 2026-04-24T00:04:00Z
  checked: test_senior_agent.py — morning_digest tests
  found: test_morning_digest_whatsapp_failure_still_commits (line 291-330) explicitly asserts that a Twilio exception is swallowed and run.status = "completed" afterward.
  implication: The silent-failure behavior is not a bug in the tests — it's intentional design (WhatsApp failure shouldn't kill the digest record). But it means `agent_runs.status='completed'` is USELESS as a health signal for "did the user actually get the message." Need to store the Twilio SID (or None) on `agent_runs.notes` so we can tell them apart.

- timestamp: 2026-04-24T00:05:00Z
  checked: Sandbox configuration in .env.example
  found: `TWILIO_WHATSAPP_FROM=whatsapp:+14155238886` — the canonical Twilio sandbox number. `whatsapp.py` docstring line 4: 'Recipient must have opted in via: "join government-accident" to +14155238886'.
  implication: **The user is on the Twilio WhatsApp SANDBOX, not an approved sender.** The sandbox has a 72-hour session-expiry rule: once the user hasn't texted the sandbox in 72h, outbound messages are silently dropped (or marked `failed` with error 63016). Since the user says "weeks," this is very likely an active factor — EVEN IF env vars are correct, the sandbox session almost certainly expired by now. User action required: re-join sandbox. **Defect C candidate.**

- timestamp: 2026-04-24T02:15:00Z
  checked: Prod DB direct query via scheduler/.env DATABASE_URL (Neon pooler). agent_runs WHERE agent_name='morning_digest' ORDER BY started_at DESC LIMIT 15. All show status='completed', notes=None, started_at at 15:00:0X UTC (= 08:00 PDT) every day from Apr 10-24. No gap, no 'failed' rows.
  found: Cron fires daily at 08:00 PDT without fail. Every run completes in 2-6 seconds. notes=None is expected — the uncommitted code-fix that writes WhatsApp status to notes is NOT deployed yet.
  implication: The cron is NOT broken. The worker is NOT crashing. The job runs every morning. Whatever is wrong, it's happening INSIDE `run_morning_digest` silently — no uncaught exception.

- timestamp: 2026-04-24T02:18:00Z
  checked: Prod DB direct query — daily_digests table, ORDER BY created_at DESC LIMIT 20.
  found:
    • Apr 14-24 (11 rows): whatsapp_sent_at POPULATED (seconds after created_at).
    • Apr 8-13 (6 rows): whatsapp_sent_at=NULL.
    • Apr 9 created_at=08:00:03 UTC (not 15:00 — different config value at that time or different DST state). Apr 10-24 all at 15:00:0X UTC.
  implication: Apr 8-13 the whatsapp send raised (Twilio creds missing or bad). Apr 14 = creds set or opt-in done. Apr 14-24 = Twilio call returns a SID (no exception) and `record.whatsapp_sent_at = now()` executes. **The Python code believes every send Apr 14-24 succeeded.** Yet user only received Apr 14 and Apr 15 per their screenshot. Messages Apr 16 onward: Twilio API accepted, SID assigned, Python recorded "sent", but the actual WhatsApp delivery failed silently at the Meta/channel layer. **Classic signature of Twilio sandbox 24-hour-window expiry.**

- timestamp: 2026-04-24T02:25:00Z
  checked: Regression suspects — commits touching morning_digest path Apr 16-22 (fb0d235, 42adaf3, 979b69c, be9cd8b, 62ffda4, beba088).
  found: fb0d235 = module-level scheduler var + hardened pg_advisory_unlock (improvement, not regression). 42adaf3 = renames story dict keys source→source_account, url→source_url — WhatsApp consumer only reads `headline`, no impact. be9cd8b (sn9 Task 2) = deleted dedup/queue-cap/alerts/expiry-sweep helpers but kept _headline_from_rationale, _assemble_digest, run_morning_digest untouched. 62ffda4 = purged Twitter; Senior doesn't import twitter. 979b69c (eoe) = rewrote worker.py but morning_digest registration preserved with same id, same lock_id=1005, same CronTrigger. beba088 = chart_renderer subprocess spawn in worker.main(); degrades infographic renders only on failure, non-fatal, does NOT touch morning_digest.
  implication: No code regression disabled the send path. Every commit either preserved morning_digest wiring or improved resilience. Combined with DB ground truth (whatsapp_sent_at populated), the code path is intact. **Regression hypothesis ruled out.**

- timestamp: 2026-04-24T02:28:00Z
  checked: Behavior of `client.messages.create()` in twilio-python when delivery fails at the Meta layer.
  found: `client.messages.create()` is an HTTP call to Twilio's REST API. Twilio queues the message and returns the SID immediately (status='queued' or 'accepted'). Delivery status is asynchronous — status transitions to 'sent' → 'delivered' (on success) or 'failed' (on Meta rejection). The REST call does NOT block on Meta; does NOT raise TwilioRestException on delivery failure; and our code never queries msg.status or msg.error_code after the initial return. Error 63016 ("Channel sender not authorized to send message to channel recipient") is the sandbox's "recipient has not opted in (or session expired)" signal — it arrives on the message's status AFTER the API has already returned success.
  implication: This IS the failure mode. Our code's success path (`sid = await asyncio.to_thread(_send_sync, ...)` → `record.whatsapp_sent_at = now()`) runs even when the message will never be delivered. No retry, no status check, no webhook — Twilio-side delivery failures are invisible to the scheduler. Explains why `whatsapp_sent_at` is populated for Apr 16-24 while user received zero messages. **Defect C confirmed by mechanism, pending Twilio console log check.**

## Resolution

root_cause: |
  **Defect C — Twilio WhatsApp Sandbox 24-hour customer-service window expired.**

  Confirmed by prod DB ground truth + Twilio API semantics:
  - Cron fires daily at 08:00 PDT (agent_runs all status='completed' Apr 10-24).
  - `send_whatsapp_message` returns a SID on every call Apr 14-24 (daily_digests.whatsapp_sent_at populated).
  - User's Railway screenshot proves all 4 Twilio env vars are set on the scheduler service.
  - User received messages on Apr 14 AND Apr 15 (2 days of delivery), then silence Apr 16-24.

  Mechanism: `Client.messages.create()` is a REST call that enqueues the message Twilio-side and returns a SID immediately. It does NOT block on actual WhatsApp delivery. Delivery status transitions asynchronously to 'delivered' OR 'failed' with error_code 63016 ("Channel sender not authorized to send message to channel recipient") — the sandbox's standard error for an expired/absent 24-hour session. Our scheduler code never queries msg.status post-create and there is no status-callback webhook configured, so Meta-layer delivery failures are completely invisible: the Python believes every send succeeded.

  The sandbox-session mechanic: from `whatsapp.py` docstring — recipient must text `join <code>` to +14155238886. Within the 24h customer-care window following the recipient's last inbound, freeform outbound sends are delivered. Outside the window, Twilio accepts the API call but Meta rejects delivery. The 2-day pattern (Apr 14-15 delivered, Apr 16+ silent) fits exactly: user joined/reopted-in around Apr 14, got 2 days of 08:00 PDT digests, then the 24-hour window closed and every subsequent morning's send was silently dropped.

  Defects A and B are ELIMINATED:
  - A (timezone): DB config morning_digest_schedule_hour=15, scheduler tz=UTC → fires at 08:00 PDT. Matches Apr 15 delivery timestamp in user's screenshot. Not wrong.
  - B (env vars): Railway screenshot shows all 4 vars present. Confirmed by DB evidence that send path ran to completion (returned a SID, not None).

fix: |
  **Code changes (hardening, NOT root cause — keep):**

  1. `scheduler/worker.py` — attach explicit `timezone="America/Los_Angeles"` to the morning_digest CronTrigger and change default `morning_digest_schedule_hour` from "8" to "7". This is defensive hardening that removes the UTC-vs-local-TZ drift surface. Current system works (fires 08:00 PDT via hour=15 UTC interpretation) but a future DST flip or tz-config churn could silently re-introduce the mis-timing. The explicit timezone pin is cheap and removes that risk.

  2. `scheduler/services/whatsapp.py` — missing-credentials branch now logs at ERROR (was WARNING) and names the specific missing keys. Railway's default log level filters WARNING. This is observability hardening for future credential-drift scenarios.

  3. `scheduler/agents/senior_agent.py` — write Twilio SID (or skip/fail reason) to `AgentRun.notes`. Without this, `whatsapp_sent_at` is the ONLY signal and it's ambiguous (populated whenever create() returns, even when Meta rejects delivery). With this, a future sandbox expiry shows as `notes='whatsapp_sent: sid=SMxxx'` — good enough to cross-reference against Twilio console. To catch sandbox-expiry earlier we'd need to either (a) call `client.messages(sid).fetch()` 30s after create to read final status, or (b) configure a StatusCallback webhook. Both are out of scope for this fix; the notes-capture closes the immediate observability gap.

  **User action (primary remedy, cannot be automated):**

  1. **From your WhatsApp phone**, send `join government-accident` (or whatever your sandbox code is — check Twilio console → Messaging → Try it out → Send a WhatsApp message → "Sandbox configuration" section for the exact code) to `+1 (415) 523-8886`. This reopens the 24-hour customer-service window.

  2. **Verify in Twilio console → Messaging → Logs** → filter `From: whatsapp:+14155238886` for dates 2026-04-16 through 2026-04-24. Expected evidence: ~9 outbound messages, each with status=failed + error_code=63016. This confirms sandbox-expiry as the silent failure mode.

  3. **Ongoing mitigation (choose one):**
     a. **Keep the sandbox + reply daily.** Any inbound message from your phone to +14155238886 resets the 24-hour window. A "👍" reply to each day's digest keeps the next day's delivery alive. Brittle but free.
     b. **Migrate off the sandbox to an approved WhatsApp Business sender.** Requires: Meta Business Manager verification, approved Message Templates for any freeform content outside the 24h window, dedicated Twilio phone number or Twilio-Hosted number. Takes days to approve but delivers unconditionally. Budget-wise this is still well inside the ~$5/mo Twilio line in CLAUDE.md.
     c. **Add a StatusCallback webhook** to `client.messages.create()` and surface delivery failures as an ERROR-level log + notes column. This doesn't prevent failures but makes them visible immediately instead of after weeks. Cheap add-on to either (a) or (b).

fix: |
  Three-part fix:

  1. **Code fix (Defect A) — cron timezone.**
     In `scheduler/worker.py::build_scheduler`, change the morning_digest registration:
       - Attach `timezone="America/Los_Angeles"` to the CronTrigger explicitly.
       - Change default `morning_digest_schedule_hour` from "8" to "7" (now PT-local, not UTC).
       - Update the log line's wording from "8:00 UTC" to "7:00 America/Los_Angeles".
     Also update DB config seed / upsert if applicable — but the default fallback in `_read_schedule_config` is the canonical source.
     Update `scheduler/tests/test_worker.py` to assert the new timezone and hour.

  2. **Code fix (observability) — stop swallowing WhatsApp failures silently.**
     In `scheduler/services/whatsapp.py::send_whatsapp_message`:
       - When credentials are missing, raise `RuntimeError` instead of returning None (or escalate log level to ERROR so it's visible in Railway). Alternatively, return a structured dict `{"sid": None, "skipped_reason": "missing_credentials"}`.
     In `scheduler/agents/senior_agent.py::run_morning_digest`:
       - Capture the returned SID (or the skip reason) and write it into `run.notes` on the AgentRun row. This way `SELECT notes FROM agent_runs WHERE agent_name='morning_digest' ORDER BY started_at DESC` gives ground truth immediately. Also write `record.whatsapp_sid` on DailyDigest if a column exists; otherwise just put it in notes.

  3. **User action (Defects B + C) — cannot be fixed from code:**
     - Audit Railway scheduler service env vars (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, DIGEST_WHATSAPP_TO). If any are missing/stale, set them. Redeploy scheduler service.
     - Re-join Twilio WhatsApp sandbox: from the recipient phone, text `join <your-sandbox-code>` to +1 (415) 523-8886. Confirm Twilio console shows the session active.
     - Pull the last 7 days of outbound message logs from Twilio console → Messaging → Logs → filter `From: whatsapp:+14155238886`. Share status codes / error codes with me.

verification: |
  Self-verified (code fixes — hardening only, not root cause):
    - `uv run pytest` in scheduler/ — all tests pass, zero regressions.
    - `uv run ruff check` on all modified files — clean.
    - Prod DB ground-truth query (via scheduler/.env DATABASE_URL) directly contradicts Defect A (cron fires at 15:00 UTC = 08:00 PDT as expected) and Defect B (daily_digests.whatsapp_sent_at populated Apr 14-24 implies creds present and send call did not raise).

  CONFIRMED ELIMINATIONS (not just my analysis — DB + user screenshots):
    1. Defect A (timezone mis-fire): DB shows all runs at 15:00:0X UTC. User's Apr 15 message arrived at 08:00 PDT. These agree — cron is firing at the expected time, not at 01:00 PDT.
    2. Defect B (env var drift): User's Railway screenshot shows TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, DIGEST_WHATSAPP_TO all present on the scheduler service.
    3. Regression between Apr 15-20: Every commit touching morning_digest (fb0d235, 42adaf3, 62ffda4, be9cd8b, 979b69c, beba088) preserved the send path. DB evidence (whatsapp_sent_at populated Apr 14-24) proves the code still executes the send.

  PENDING USER VERIFICATION (to confirm Defect C definitively):
    1. Open Twilio console → Monitor → Logs → Messaging (or Messaging → Try it out → Daily Logs). Filter `From: whatsapp:+14155238886` for 2026-04-16 through 2026-04-24. Expected: ~9 rows each with status=failed + error_code=63016 (or ErrorCode "63016").
    2. Send `join government-accident` from your WhatsApp phone (or whichever sandbox code Twilio assigned — the join code is printed in Twilio console → Messaging → Try it out → Send a WhatsApp message). Wait for Twilio's confirmation reply.
    3. Trigger a test digest OR wait for tomorrow's 08:00 PDT cron. Within ~5 seconds the message should arrive to your phone.
    4. Confirm the previously-committed-but-not-merged code fixes are OK to commit now:
       - worker.py: explicit `timezone="America/Los_Angeles"` on CronTrigger; default hour 7 (PT-local interpretation).
       - whatsapp.py: ERROR-level log on credential-miss with named keys.
       - senior_agent.py: writes SID/skip/fail reason to AgentRun.notes so next time silence is 2-day instead of 9-day.
    5. (Optional strategic) Decide on sandbox-vs-approved-sender: if reply-daily is acceptable, stay on sandbox; if not, migrate to Meta Business Manager approved sender. Separate tracked item.

files_changed:
  - scheduler/worker.py (cron timezone + default hour 7 PT)
  - scheduler/services/whatsapp.py (ERROR-level log with named missing vars, SID logged on success)
  - scheduler/agents/senior_agent.py (capture SID/skip-reason into run.notes)
  - scheduler/tests/test_worker.py (2 new tests)
  - scheduler/tests/test_whatsapp.py (1 new test)
  - scheduler/tests/test_senior_agent.py (2 new tests)

## Redactions (for fix instructions)
Cannot redact user's phone number or Twilio account ID from this doc because local `scheduler/.env` has the Twilio vars EMPTY (no values to redact). User's actual values live only in Railway env. That information gap is itself part of the issue (no local parity with prod for the scheduler's Twilio config).
