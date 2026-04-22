# quick-260422-vxg — Multi-Agent Cadence Rebalance

**Status:** Verified (local) — pending Railway deploy
**Branch:** `quick/260422-vxg-cadence-rebalance-7-sub-agents` (parent = `ddb5721`)
**Implementation commit:** `68b21d1`
**Planning commit:** (to be added)
**Date:** 2026-04-22

---

## Task

Rebalance the 7-sub-agent cron topology to match the operator's updated cadence strategy, tighten the Quotes drafter to surface exactly one quote per day (was two), and install a drafter-level analyst/economist quality gate on the Gold Media (video_clip) sub-agent.

---

## Scope (in)

### 1. `scheduler/worker.py` — topology rebalance

**Before (mos state):**
- 6 interval agents + 1 cron agent (sub_quotes daily noon PT).
- Interval cadence: BN=1h, others=2h.
- Offsets: `[0, 17, 34, 68, 85, 102]` min.

**After (vxg state):**
- 3 interval agents + 4 cron agents.
- Interval cadence: BN=2h, Threads=4h, Long-form=4h. Offsets: `[0, 17, 34]`.
- Cron agents (all 12:00 America/Los_Angeles):
  - `sub_quotes` — daily.
  - `sub_infographics` — daily.
  - `sub_video_clip` ("Gold Media") — daily.
  - `sub_gold_history` — every other day via `day="*/2"`.

**Schema upgrade for `CONTENT_CRON_AGENTS`:**
From fixed 7-tuple `(job_id, run_fn, name, lock_id, hour, minute, timezone)` → 5-tuple `(job_id, run_fn, name, lock_id, cron_kwargs: dict)`.

The 5th field is a CronTrigger kwargs dict so heterogeneous cron patterns (daily vs every-other-day) coexist cleanly. Registration loop calls `CronTrigger(**cron_kwargs)`.

**Module docstring + startup log line** updated to reflect the new 3-interval / 4-cron topology.

### 2. `scheduler/agents/content/quotes.py`

- `max_count=2` → `max_count=1` in `run_draft_cycle`.
- Docstring "top-2" → "top-1".
- REPUTABLE_SOURCES whitelist (from mos) unchanged.
- `_draft` quality-gate prompt unchanged.

### 3. `scheduler/agents/content/video_clip.py` — Gold Media analyst quality gate

- **`VIDEO_ACCOUNTS` reorder + trim:** analyst-interview-heavy media first — `["Kitco", "CNBC", "Bloomberg", "BloombergTV", "ReutersBiz", "FT", "MarketWatch"]`. Dropped `BarrickGold`, `WorldGoldCouncil`, `Mining`, `Newaborngold` (corporate/sector accounts, PR-sourced, not analyst commentary).
- **`_draft_video_caption` quality bar** added to the user_prompt with 3 criteria (speaker credibility: named analyst/economist with tier-1 affiliation; substance: specific view or forecast; freshness: current commentary). Reject path returns `{"reject": true, "rationale": "..."}` → function returns None.
- **`run_draft_cycle`** iterates up to `MAX_DRAFT_ATTEMPTS = 5` most-recent candidates (sorted by `created_at` desc with `datetime.min.replace(tzinfo=timezone.utc)` fallback to avoid tz-naive comparison crashes). Breaks after first successful persist — goal is 1 analyst clip/day; if none passes the bar, none queued.

### 4. `scheduler/agents/content/breaking_news.py`

- Module docstring L3 reverted from "every 1 hour" (m9k) → "every 2 hours" (vxg).
- No functional change.

### 5. `scheduler/agents/content/gold_history.py`

- Module docstring cadence line replaced with `day='*/2'` every-other-day noon PT reference.
- No functional change to picker / `_verify_facts` / `_draft_gold_history` / `_add_used_topic`.

### 6. Tests

**`scheduler/tests/test_worker.py`:**
- Rescoped `test_sub_agents_total_seven` — now `len(INTERVAL) == 3` and `len(CRON) == 4`.
- Trimmed `test_sub_agent_staggering` offsets assertion to `[0, 17, 34]`.
- Rewrote `test_quotes_is_daily_cron` for dict-shape cron tuple.
- Added `test_interval_agents_cadences` — asserts `[2, 4, 4]` interval_hours.
- Added `test_cron_agents_count_four`.
- Added `test_cron_agents_use_dict_shape`.
- Added `test_gold_history_is_every_other_day` — asserts `cron_kwargs["day"] == "*/2"`.
- Added `test_infographics_is_daily_cron`.
- Added `test_video_clip_is_daily_cron`.

**`scheduler/tests/test_quotes.py`:**
- `test_run_draft_cycle_passes_filters` asserts `max_count == 1`.

**`scheduler/tests/test_video_clip.py`:**
- Added `test_video_accounts_reordered_analyst_first`.
- Added `test_draft_video_caption_returns_none_on_reject`.

---

## Scope (out, explicitly deferred)

- **Infographics historical-fallback drafter.** User's original request for infographics was "try to link to relevant news from that day. If it can't then create some very interesting historical infographics." Per user's "Option A" directive, this task ships **cadence + max_count only** for infographics. The historical-fallback drafter (Claude picker + `infographics_used_topics` config + drafter + integration into run_draft_cycle, modeled on gold_history.py architecture) is deferred to a separate future quick task.
- **Gold Media source switch to podcast/interview sources.** User's original request mentioned "1 podcast/interview of a financial analyst or economist talking about gold and the price." Per "Option A" directive, this task keeps the existing X API video source and tightens the account list + adds the analyst quality bar. A switch to YouTube Data API / podcast RSS / alternate source is deferred.
- Any changes to breaking_news/threads/long_form/quotes/infographics drafters beyond docstrings + scheduling.
- Any DB schema changes, Alembic migrations, or new Config keys.
- Any frontend changes.

---

## Constraints respected

- `uv run ruff check .` (scheduler) — clean.
- `uv run pytest -x` (scheduler) — 90 passed (baseline 82 + 8 net new). Gate required ≥87, comfortably met.
- Zero behavior change to the 4 other sub-agents using `run_text_story_cycle` (threads, long_form, infographics) — their `run_draft_cycle` calls still pass no `max_count` / `source_whitelist`, so defaults=None behavior preserved.
- Zero DB schema changes.
- Zero new environment variables.
- DST-aware scheduling preserved (timezone="America/Los_Angeles" handles PST/PDT).
- `JOB_LOCK_IDS` unchanged (still 8 keys, morning_digest + 7 sub-agents at 1005/1010-1016).

---

## Validation greps (all passed)

1. `grep "CronTrigger" scheduler/worker.py` — import + `CronTrigger(**cron_kwargs)` in registration loop.
2. `grep "day.*\\*/2" scheduler/worker.py` — gold_history every-other-day kwarg visible.
3. `grep "sub_quotes" scheduler/worker.py` — appears only in CONTENT_CRON_AGENTS (not intervals).
4. `grep "America/Los_Angeles" scheduler/worker.py` — 4 timezone kwargs (one per cron agent).
5. `grep "MAX_DRAFT_ATTEMPTS" scheduler/agents/content/video_clip.py` — 5-attempt cap defined + used.
6. `grep "reject" scheduler/agents/content/video_clip.py` — reject path in `_draft_video_caption`.
7. `grep "max_count=1" scheduler/agents/content/quotes.py` — confirms quotes cap dropped to 1.
8. `grep -c "BloombergTV\\|ReutersBiz\\|MarketWatch" scheduler/agents/content/video_clip.py` — new analyst-heavy VIDEO_ACCOUNTS entries present.

---

## Gates

- **Scheduler ruff:** `All checks passed!`
- **Scheduler pytest:** `90 passed, 13 warnings in 0.75s` (baseline 82; 8 net new).
- **Ruff warnings unchanged from baseline** — pre-existing `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited` preserved as-is (out of vxg scope).

---

## Deviations from plan

None. Plan executed verbatim.

**Conditional work notes:**
- Plan task 2c-2f (threads/long_form/infographics/video_clip cadence docstring touches) were gated on grep hits. Only `breaking_news.py` contained a cadence docstring matching the pattern (reverting the m9k "every 1 hour" line). Other sub-agent module docstrings did not mention cadence, so they were correctly skipped — matches the plan's "skip files that don't mention cadence" directive.
- `MAX_DRAFT_ATTEMPTS=5` was added as a local variable inside `run_draft_cycle` (matching the plan's code block exactly); could be lifted to a module-level constant if desired in a follow-up.

---

## Post-deploy expectations (operator confirms on Railway)

On next scheduler redeploy:

1. **Startup log** should show 7 jobs scheduled — 3 interval + 4 cron — plus `morning_digest`. Each cron line should list the agent name + cadence label (daily 12:00 / every 2 days 12:00 America/Los_Angeles).
2. **Next 12:00 America/Los_Angeles tick** fires `sub_quotes`, `sub_infographics`, and `sub_video_clip` (plus `sub_gold_history` on even days).
3. **Within 2h of boot** (offset=0 + 10s buffer from m9k): `sub_breaking_news` first fire logged as an agent_run row; `/agents/breaking-news` page shows the "Pulled from agent run at {time}" header.
4. **Threads + long_form** each fire within 4h of boot at their staggered offsets (17m + 34m past boot for first fire respectively), and every 4h thereafter.
5. **Quotes daily fire (12:00 PT)** logs: reputable filter + max_count=1 cap funnel + either 1 quote draft OR 0 drafts with reject rationale.
6. **Gold Media daily fire (12:00 PT)** logs: up to 5 analyst-first candidates evaluated, reject rationale per non-analyst candidate, break after first successful persist OR 0 if none passes the bar.
7. **Infographics daily fire (12:00 PT)** logs: up to 2 bundles from matching news stories (historical-fallback not yet implemented — empty day if no relevant news).
8. **Gold History** fires only on even calendar days (edge case: 31-day-month transitions can compress back-to-back on day 1 of the next month — documented as acceptable behavior).

---

## Why bundled into one task

All 7 sub-agents share `scheduler/worker.py` registration. Splitting cadence changes per-agent would force 7 tickets with duplicate planning + test runs. The CONTENT_CRON_AGENTS schema upgrade is a prerequisite for 3 of the 4 cron moves (infographics/video_clip/gold_history) — cannot ship them incrementally without either keeping dual schemas or re-migrating three times. Video Clip's analyst bar + VIDEO_ACCOUNTS reorder are inseparable from the "1 podcast/interview/day" intent.

---

## Files touched

| File | Change |
|------|--------|
| `scheduler/worker.py` | Topology rebalance (3 interval + 4 cron), CONTENT_CRON_AGENTS schema upgrade to dict-of-kwargs, registration loop unpacks 5 fields, startup log + docstring refresh |
| `scheduler/agents/content/breaking_news.py` | Docstring L3 reverted "every 1 hour" → "every 2 hours" (undoes m9k 1h experiment) |
| `scheduler/agents/content/gold_history.py` | Docstring cadence line replaced with `day='*/2'` every-other-day noon PT reference |
| `scheduler/agents/content/quotes.py` | `max_count=2 → 1`, docstring "top-2 → top-1" |
| `scheduler/agents/content/video_clip.py` | VIDEO_ACCOUNTS reorder/trim to 7 analyst-heavy handles, `_draft_video_caption` adds 3-criterion quality bar + reject path, `run_draft_cycle` sorts clips desc / caps to MAX_DRAFT_ATTEMPTS=5 / breaks after first persist |
| `scheduler/tests/test_worker.py` | 3 existing tests rescoped, 6 new tests added |
| `scheduler/tests/test_quotes.py` | 1 test assertion updated (max_count=1) |
| `scheduler/tests/test_video_clip.py` | 2 new tests added |
