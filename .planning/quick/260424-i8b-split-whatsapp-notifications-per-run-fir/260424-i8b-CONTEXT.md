# Quick Task 260424-i8b: Split WhatsApp notifications (firehose + digest) — Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Task Boundary

Split WhatsApp notifications into two streams:

**STREAM 1 — Per-run firehose for breaking_news + threads**
- When `sub_breaking_news` or `sub_threads` completes a run with ≥1 approved-for-drafting item, send 1 WhatsApp listing ALL approved tweets from that run.
- Fires every 2h per agent → up to 12 WhatsApps/day per agent. User-confirmed intended firehose.
- Empty runs (0 items) send NO WhatsApp. Silence = nothing to notify.

**STREAM 2 — 12:30 PT daily digest for infographics + quotes + gold_media + gold_history**
- Retime existing `morning_digest` job from 07:00 → 12:30 America/Los_Angeles.
- Redirect content: summarize ONLY infographics + quotes + gold_media + gold_history.
- Breaking_news + threads are excluded from the digest (they're already in Stream 1).

**Out of scope (Phase B, separate /gsd:quick session):**
- Approve→auto-post-to-X pipeline
- `draft_items.approval_state` state machine
- Backend API endpoint + frontend approve button
- `CLAUDE.md` auto-post override

</domain>

<decisions>
## Implementation Decisions

### Message format (Stream 1)
**Locked:** Numbered list.

Format template:
```
[<agent_name>] <N> approved:
1. <tweet text>
2. <tweet text>
3. <tweet text>
```

Rationale: compact, readable, numbers map 1:1 to dashboard order so user can reference "item 2" when approving on Vercel.

### Long-payload chunking (Stream 1, threads agent)
**Locked:** Split into multiple WhatsApp messages on tweet boundaries.

- Twilio WhatsApp hard limit: 1600 chars/message
- Working budget per chunk: 1500 chars (reserve 100 for chunk header + safety margin)
- Chunk header format: `[threads 1/2]`, `[threads 2/2]` (continuation pattern)
- Breaking_news messages rarely exceed 1600 chars (≤10 items × ~280 char tweet = ~2800 max, but typical runs are 3-5 items × ~280 = ~1400) — still apply the same chunking logic defensively
- Never split an individual tweet across messages — chunk boundary must sit between tweets

### Digest time (Stream 2)
**Locked:** 12:30 America/Los_Angeles.

CronTrigger: `hour=12, minute=30, timezone="America/Los_Angeles"` — consistent with the explicit-TZ pattern landed in debd4ef.

### Hook location (Stream 1)
**Claude's discretion + research correction — locked to `scheduler/agents/content/__init__.py:run_text_story_cycle`.**

**CORRECTION from initial CONTEXT assumption:** Research confirmed that `sub_breaking_news` and `sub_threads` completions do NOT flow through `senior_agent.py` — they complete inside `run_text_story_cycle` in `scheduler/agents/content/__init__.py`. This is the actual completion path for both firehose agents.

Implementation shape:
- Insert hook inside `run_text_story_cycle` AFTER `agent_run.status = "completed"` (around line 373, before the surrounding `except` block).
- Use the `items_queued` counter (line ~326) — accumulator already tracks approved-for-drafting items in scope. NO extra DB query needed; the items' text is already in `draft_content` in scope.
- Fire only when `agent_name in {"sub_breaking_news", "sub_threads"}` AND `items_queued > 0`.
- Use `await services.whatsapp.send_agent_run_notification(...)` — matches the canonical `await send_whatsapp_message(...)` pattern from `senior_agent.py:281`. Do NOT use `asyncio.create_task` (would orphan relative to the `async with AsyncSessionLocal()` block).
- `agent_run.notes` is a JSON dict (`{"candidates": N, ...}`) — MERGE the whatsapp status into the dict, do NOT concat as string. Example: `agent_run.notes = {**existing_notes, "whatsapp_per_run_sent": sid}` or `"whatsapp_per_run_failed": <error>` / `"whatsapp_per_run_skipped": <reason>`.
- Keep notes distinct from `send_morning_digest`'s `whatsapp_sent` key so the two notification paths are observably separate.

Rationale for insertion point over sub-agent files: keeps sub_breaking_news.py and sub_threads.py at ZERO DIFF (honors preservation invariants). The shared `content/__init__.py` wrapper is the natural seam.

**Scope update:** `scheduler/agents/content/__init__.py` MUST be added to MODIFY list. Hook dispatch stays in `content/__init__.py`.

### Digest scope filter (Stream 2) — runtime enforcement
**Locked (revision iteration 1):** The digest scope filter is ENFORCED at runtime — not documentation-only.

Without a runtime filter, the 12:30 digest would still include breaking_news + threads content, duplicating what Stream 1 already sent 30 min earlier at the 12:00 runs. That defeats the two-stream design.

**The runtime filter is minimal — a SQL/Python filter restricting the digest query to `content_type IN ('infographic', 'quote', 'gold_media', 'gold_history')` (equivalently: excluding `content_type IN ('breaking_news', 'thread')`) or equivalent narrow filter via `agent_runs.agent_name`. Hook dispatch stays in `content/__init__.py`.**

Because `DraftItem` has no `agent_name` column (see `scheduler/models/draft_item.py`) but `ContentBundle.content_type` maps 1:1 to the source sub-agent (`breaking_news`, `thread`, `quote`, `infographic`, `gold_media`, `gold_history` — see `scheduler/models/content_bundle.py:15`), the narrow-diff filter goes on the `_assemble_digest` queries in `senior_agent.py`. Concretely: filter the `top_stories` and `yesterday_approved/rejected/expired` queries to exclude items sourced from breaking_news + threads bundles, either via a join to `ContentBundle` or (simpler) via an `EXISTS` / `IN` subquery scoped on `ContentBundle.content_type`.

**Narrow-diff constraint on `senior_agent.py`:** the ONLY allowed change is the digest-content query filter (excluding `content_type IN ('breaking_news', 'thread')` from `_assemble_digest`'s `DraftItem` queries), plus a minimal parameterization so the executor can wire the exclusion list from `worker.py` (e.g., a defaulted constructor kwarg on `SeniorAgent` OR a module-level `DIGEST_EXCLUDED_CONTENT_TYPES` frozenset read inside `_assemble_digest`). Do NOT touch:
- The `run_morning_digest` orchestration structure beyond the function name (rename to `run_midday_digest` is allowed if it stays a trivial 1:1 rename; otherwise keep the name)
- The WhatsApp message body / prefix (`📊 Morning Digest`) unless the rename is zero-churn
- The config seeder
- Any helper that isn't touched by the filter

### Failure mode (Stream 1 + Stream 2)
**Claude's discretion — locking to silent-continue with notes annotation.**

If Twilio fails (credentials missing, sandbox expired, rate limited, network error):
- Agent run completes with `status='ok'` (the content work succeeded — missing notification is not a data failure).
- `agent_runs.notes` records the failure: `whatsapp_per_run_failed: <error>` or `whatsapp_skipped: <reason>`.
- Logger emits ERROR-level log (same hardening as `debd4ef`).
- No retry inside the job (a 2h cadence means the next run will re-try naturally; accumulating retries risks rate-limit storms).

### De-duplication (Stream 1)
**Claude's discretion — locking to agent_runs.id scoping.**

Each WhatsApp lists ONLY items whose `draft_items.agent_run_id == this_run_id`. This prevents:
- Re-notifying items from the previous run if this run's insert transaction is partially committed when the notification fires.
- Double-notifying if the runner is retried (APScheduler misfire grace period).

### Timezone consistency
**Locked:** `America/Los_Angeles` on every CronTrigger / IntervalTrigger that was timezone-ambiguous. Pattern inherited from debd4ef.

### Digest content rename (Stream 2)
**Locked:** Keep the function name `send_morning_digest` for minimal-diff (rename is churn without value), but:
- Internal docstring updated to "midday digest covering infographics + quotes + gold_media + gold_history"
- Message body prefix updated from "Good morning" to something time-neutral like "[midday digest] Today's non-firehose content:"
- The JOB identifier in APScheduler can be renamed to `midday_digest` to reflect the new cadence — low-risk rename, no DB migration

### Claude's Discretion
- Function/job identifier: `send_midday_digest` or keep `send_morning_digest` — executor picks whichever minimizes diff (leaning: keep function name, rename job to `midday_digest` for APScheduler clarity).
- Chunk numbering when only 1 chunk is needed: skip the `[X 1/1]` header (simpler for the common case).
- Exact WhatsApp message phrasing (single-line banner format) — match existing `send_morning_digest` style.

</decisions>

<specifics>
## Specific Ideas

**Scope constraints — MODIFY (required):**
- `scheduler/worker.py` — retime digest job from 07:00→12:30 PT, rename job id to `midday_digest`, declare `DIGEST_EXCLUDED_CONTENT_TYPES` constant and wire it into the `SeniorAgent` digest job
- `scheduler/services/whatsapp.py` — add `send_agent_run_notification(agent_name, items, run_id)` helper with tweet-boundary chunking (≤1500 chars/chunk)
- `scheduler/agents/content/__init__.py` — insert per-run WhatsApp dispatch after `agent_run.status = "completed"` in `run_text_story_cycle` (research-confirmed hook point, ~line 373)
- `scheduler/agents/senior_agent.py` — **NARROW-DIFF ONLY**: add digest-query filter excluding `content_type IN ('breaking_news', 'thread')` from `_assemble_digest`'s DraftItem queries (via ContentBundle join/subquery), plus a minimal way for `worker.py` to pass in the exclusion list. Nothing else in this file may change. See Digest scope filter decision above for the exact constraint.
- `scheduler/tests/test_worker.py` — extend for 12:30 cron assertion + digest-scope filter
- `scheduler/tests/test_whatsapp.py` — new tests for chunking + per-run helper (single-chunk no-prefix, multi-chunk headers, 1500-char boundary)
- `scheduler/tests/test_content_wrapper.py` or extend existing content test module — dispatch triggering (agent_name filter + items_queued>0 guard + JSON notes merge)
- `scheduler/tests/test_senior_agent.py` — extend (or create) to assert the digest-query filter: when DB contains ONLY breaking_news + thread content bundles, `_assemble_digest` returns empty `top_stories` and zero `yesterday_approved/rejected/expired` counts

**Scope constraints — ZERO DIFF (verify via `git diff main --`):**
- `scheduler/agents/content/breaking_news.py`
- `scheduler/agents/content/threads.py`
- `scheduler/agents/content/quotes.py`
- `scheduler/agents/content/infographics.py`
- `scheduler/agents/content/gold_media.py`
- `scheduler/agents/content/gold_history.py`
- `scheduler/agents/content_agent.py`
- `backend/`, `frontend/`, `alembic/`, models

**Research phase must investigate:**
- Tweepy v2 `Client.create_tweet` (for Phase B readiness):
  - OAuth 1.0a User Context required (bearer tokens = read-only on v2 writes)
  - Thread chains via `in_reply_to_tweet_id` parameter
  - Rate limits on Basic tier ($100/mo)
  - `media_ids` for attached images (if threads ever ship with images)
- Twilio WhatsApp message segmentation:
  - Is there a native Twilio flag for auto-segmentation or do we have to chunk manually?
  - How does the receiver see multiple messages — is there a conversation thread grouping?
- APScheduler async-safety:
  - Can we call `await services.whatsapp.send_...()` inside a sync job function? (Probably no — need `asyncio.run_coroutine_threadsafe` or a blocking wrapper.)
  - Does the existing `morning_digest` path call WhatsApp sync or async? (Grep `services/whatsapp.py` usage.)

**Validation gates:**
```bash
cd scheduler && uv run pytest -x                                              # all green
cd scheduler && uv run pytest tests/test_whatsapp.py tests/test_worker.py tests/test_senior_agent.py tests/test_content_wrapper.py -x -v   # new tests green
cd scheduler && uv run ruff check .                                            # clean

# preservation diffs (senior_agent.py is NOT in this list — narrow-diff allowed)
git diff main -- scheduler/agents/content/breaking_news.py \
               scheduler/agents/content/threads.py \
               scheduler/agents/content/quotes.py \
               scheduler/agents/content/infographics.py \
               scheduler/agents/content/gold_media.py \
               scheduler/agents/content/gold_history.py \
               scheduler/agents/content_agent.py \
               backend/ frontend/ alembic/                                    # empty

# senior_agent.py narrow-diff: ONLY digest-query filter changes, no unrelated refactors
git diff main -- scheduler/agents/senior_agent.py | grep -v "^+++" | grep -v "^---" | grep -v "^@@"
# Must show ONLY digest-query filter changes; no unrelated refactors

# cron assertion
grep -n "hour=12\|minute=30" scheduler/worker.py                              # matches
grep -n "hour=7\|hour=07" scheduler/worker.py                                 # should NOT match for digest
```
</specifics>

<canonical_refs>
## Canonical References

- `debd4ef` — morning_digest Twilio hardening (explicit TZ, ERROR logging, structured notes). Pattern to match.
- `48aad7c` — Twilio debug session artifact at `.planning/debug/twilio-morning-digest-not-delivering.md`. Root-cause documented.
- `scheduler/worker.py` — current `morning_digest` CronTrigger (07:00 PT); job registration is around line 60-110 based on prior reads.
- `scheduler/services/whatsapp.py` — current `send_morning_digest()` entry point; structure for `send_agent_run_notification` should mirror.
- `scheduler/agents/senior_agent.py` — current `agent_runs.notes` structured write (`whatsapp_sent`, `whatsapp_skipped`, `whatsapp_failed`). Pattern to extend. `_assemble_digest` is the query site that needs the content_type exclusion filter.
- `scheduler/models/content_bundle.py` — `ContentBundle.content_type` is the 1:1 mapping from sub-agent to digest row (breaking_news, thread, quote, infographic, gold_media, gold_history). The digest filter operates on this column.
- Twilio WhatsApp docs: 1600-char message limit, multi-message continuation is the standard pattern (no native segmentation flag).
- APScheduler 3.11.2 — `AsyncIOScheduler` is used in this project (per worker.py). Async jobs are natively supported; no `asyncio.run_coroutine_threadsafe` needed.
</canonical_refs>
