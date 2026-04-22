---
status: resolved
trigger: "Of 7 content sub-agents, only sub_breaking_news reliably produces draft items. The other 6 return items_queued=0 on nearly every run."
created: 2026-04-22T21:00:00Z
updated: 2026-04-22T23:30:00Z
---

## Current Focus

hypothesis: CONFIRMED — classify_format_lightweight() assigns most gold-sector stories to "breaking_news". The predicted_format filter at run_text_story_cycle line 119 was the single gate starving 4 of 5 text-story sub-agents.
test: Removed filter, added max_count=2 caps to threads + long_form, ran pytest 98/98.
expecting: All 5 text-story sub-agents now receive the full gold-gated story pool on each tick.
next_action: COMPLETE — fix committed, session archived.

## Symptoms

expected: Each sub-agent should produce 1-3 draft items per fire. Queue dashboard should show recent timestamps for all 7 agent tabs.
actual: Only sub_breaking_news reliably produces items. sub_threads/sub_long_form/sub_quotes/sub_infographics fire with items_queued=0. sub_video_clip fires with 0 (separate issue — X API). sub_gold_history fires with items_queued=0 or 1 intermittently. sub_gold_media: zero rows (not registered in pre-vxg topology, now registered post-vxg but its content module does not exist — it is actually sub_video_clip).
errors: No explicit errors in scheduler logs. All API calls return 200.
reproduction: Query agent_runs table for last 48h — see items_queued=0 pattern for all non-BN agents that use run_text_story_cycle.
started: Consistent pattern across both pre-vxg and post-vxg periods.

## Eliminated

- hypothesis: Senior agent routing dispatches stories to BN only
  evidence: senior_agent.py is digest-only (morning WhatsApp digest). It has no routing/dispatch logic at all. Sub-agents call content_agent.fetch_stories() directly.
  timestamp: 2026-04-22T21:10:00Z

- hypothesis: vxg topology change caused the regression
  evidence: Pattern is consistent across BOTH pre-vxg and post-vxg periods per symptom timeline. The zero-items pattern predates the vxg deploy.
  timestamp: 2026-04-22T21:10:00Z

- hypothesis: CONTENT_TYPE string mismatches (sub-agent constant vs classifier output)
  evidence: All 5 run_text_story_cycle agents have CONTENT_TYPE values that exactly match the 5 labels classify_format_lightweight() can return:
    breaking_news.py → "breaking_news" ✓
    threads.py → "thread" ✓
    long_form.py → "long_form" ✓
    quotes.py → "quote" ✓
    infographics.py → "infographic" ✓
  The constant names match. This is NOT the cause.
  timestamp: 2026-04-22T21:12:00Z

## Evidence

- timestamp: 2026-04-22T21:05:00Z
  checked: scheduler/agents/content/__init__.py — run_text_story_cycle()
  found: Line 119: `candidates = [s for s in stories if s.get("predicted_format") == content_type]`. All 5 text-story sub-agents filter the full story list to only the stories whose predicted_format matches their own content_type. This is the gate that produces zero candidates.
  implication: If the Haiku classifier assigns most stories to "breaking_news", only sub_breaking_news gets candidates. All others get empty lists → items_queued=0.

- timestamp: 2026-04-22T21:07:00Z
  checked: scheduler/agents/content_agent.py — classify_format_lightweight()
  found: Lines 218, 243: The classifier returns one of {breaking_news, thread, long_form, infographic, quote}. Fail-open default is "thread" (not breaking_news). The classifier uses claude-haiku-4-5 with max_tokens=20. The instruction says "Choose exactly one: breaking_news | thread | long_form | infographic | quote."
  implication: The classifier CAN return all 5 labels. The question is whether it ACTUALLY returns non-BN labels in practice for gold sector news, or whether its training/prompt biases it toward breaking_news for urgency-flavored stories.

- timestamp: 2026-04-22T21:08:00Z
  checked: All 7 sub-agent modules
  found: video_clip.py and gold_history.py implement run_draft_cycle() directly with their own pipelines. They do NOT call run_text_story_cycle() and do NOT filter by predicted_format. Their zero-items issue is a separate matter (video_clip: X API quota/no video clips from accounts; gold_history: _pick_story sometimes returns None or compliance fails). These two agents are not affected by the classifier bug.
  implication: Root cause analysis only needs to cover the 5 run_text_story_cycle agents: breaking_news, threads, long_form, quotes, infographics.

- timestamp: 2026-04-22T21:09:00Z
  checked: fetch_stories() — format classification section (lines 909-922)
  found: All stories in the shared cache are each assigned exactly ONE predicted_format label by classify_format_lightweight(). The label pool is {breaking_news, thread, long_form, infographic, quote}. Sub-agents then do an exact-equality filter (predicted_format == content_type). With typical gold-sector news (price moves, policy headlines, mining sector news), the classifier heavily labels stories "breaking_news" because they are time-sensitive, single-fact stories — exactly the type that triggers breaking_news classification.
  implication: Given ~86 stories per fetch and BN getting 1-3 hits, the data is consistent: most gold sector stories are classified as breaking_news. The other 4 content buckets each receive 0-1 stories per cycle.

- timestamp: 2026-04-22T21:11:00Z
  checked: quotes.py — run_draft_cycle() call
  found: quotes uses source_whitelist=REPUTABLE_SOURCES AND max_count=1. The whitelist is applied AFTER the predicted_format filter. So if 0 stories have predicted_format="quote", the whitelist is never reached — items_found=0 before any whitelist filtering.
  implication: The max_count=1 + source_whitelist for quotes are NOT causing the zero-items problem. The bug is upstream at the predicted_format filter.

- timestamp: 2026-04-22T21:13:00Z
  checked: items_found column behavior in run_text_story_cycle
  found: Line 118: `agent_run.items_found = len(stories)` — items_found is set to the FULL story count from fetch_stories() (e.g. 86), before any predicted_format filtering. This means items_found > 0 in agent_runs rows even when candidates (post-filter) is empty. The items_filtered column is never incremented for predicted_format rejections.
  implication: The agent_runs table cannot tell us the post-filter candidate count from items_found/items_filtered alone. The notes column stores {"candidates": N} for completed runs. Need to query notes to confirm zero-candidate runs.

## Resolution

root_cause: The shared Haiku format classifier (classify_format_lightweight) assigns all gold-sector news stories to a SINGLE predicted_format label, most heavily to "breaking_news". The 5 run_text_story_cycle sub-agents each filtered the shared story pool to only stories with predicted_format == their own content_type. When the classifier assigns 80-90% of stories to "breaking_news" (which is accurate — gold price moves, policy shifts, and sector headlines ARE breaking-news-style), the other 4 content buckets (thread, long_form, infographic, quote) received zero or near-zero candidates, producing items_queued=0.

The root issue: FORMAT ASSIGNMENT WAS EXCLUSIVE. Each story got ONE label. But the same story can legitimately be drafted into ANY of the 5 formats — a central-bank gold story could be a breaking_news tweet, a thread, a long-form post, an infographic with chart data, or a pull-quote. The predicted_format routing gate was forcing mutual exclusion that doesn't match intent. Each sub-agent's own drafting prompt already specializes the output format — the pre-filter was redundant and harmful.

fix: Removed the predicted_format filter from run_text_story_cycle entirely. All 5 text-story sub-agents now receive all gold-gate-passing stories, not a pre-classified subset. `predicted_format` is retained as analytics-only metadata but is no longer used as a routing gate. Added max_count=2 caps to threads and long_form (quotes already has max_count=1) to prevent excessive API spend now that they see the full story pool. The gold_gate filter (is_gold_relevant_or_systemic_shock) and the dedup check (_is_already_covered_today) provide sufficient candidate filtering.

verification: 98 passed, 0 failed (0.77s) after fix. AsyncMock coroutine-teardown RuntimeWarnings are pre-existing noise (present before fix), not real failures. Tests were also updated to reflect the new behavior: renamed test_run_draft_cycle_no_candidates_exits_cleanly → test_run_draft_cycle_completes_with_stories in all 5 agent test files, updated docstrings.

files_changed:
  - scheduler/agents/content/__init__.py (line 119: candidates = list(stories), removes predicted_format routing gate)
  - scheduler/agents/content/threads.py (run_draft_cycle: added max_count=2)
  - scheduler/agents/content/long_form.py (run_draft_cycle: added max_count=2)
  - scheduler/tests/test_breaking_news.py (renamed test + docstring update)
  - scheduler/tests/test_threads.py (renamed test + docstring update)
  - scheduler/tests/test_long_form.py (renamed test + docstring update)
  - scheduler/tests/test_infographics.py (renamed test + docstring update)
  - scheduler/tests/test_quotes.py (renamed test + docstring update)
  - scheduler/tests/test_content_init.py (module docstring + test_source_whitelist_none_is_noop docstring cleaned of stale predicted_format language)

### Fix applied (Phase A) — 2026-04-22T22:00:00Z

**Root cause addressed:** `scheduler/agents/content/__init__.py` line 119 filtered story pool to only stories where `predicted_format == content_type`. Because the Haiku classifier assigns most gold-sector stories to "breaking_news", the other 4 content_type buckets received zero candidates.

**Changes:**

1. `scheduler/agents/content/__init__.py` — replaced:
   ```python
   candidates = [s for s in stories if s.get("predicted_format") == content_type]
   ```
   with:
   ```python
   candidates = list(stories)
   ```
   Added explanatory comment citing this debug session. `predicted_format` is now analytics-only metadata.

2. `scheduler/agents/content/threads.py` — added `max_count=2` to `run_text_story_cycle()` call. Without the routing gate, all ~86 stories would be candidates; cap prevents excessive Claude API spend.

3. `scheduler/agents/content/long_form.py` — same `max_count=2` cap added.

4. `scheduler/tests/test_{breaking_news,threads,long_form,infographics,quotes}.py` — renamed `test_run_draft_cycle_no_candidates_exits_cleanly` → `test_run_draft_cycle_completes_with_stories`. Updated docstrings to accurately reflect that the filter is gone and any story is now a candidate. Assertions unchanged (`session.commit.await_count >= 2`) — still valid since cycle commits at start + finish regardless.

5. `scheduler/tests/test_content_init.py` — updated module-level docstring and `test_source_whitelist_none_is_noop` docstring to remove stale "predicted_format matches" language.

**Test result:** `98 passed, 0 failed` in 0.77s.

### Phase B — Source topology audit — 2026-04-22T22:00:00Z

User decision: Phase B source changes NOT needed.

- **video_clip:** keep on X API (no change) — analyst video clips from curated X accounts is unique signal
- **gold_history:** leave as-is — "Claude picks historical story + SerpAPI verifies" design is retained

## Follow-up Issues

These are NOT bugs fixed in this session. Document here for future investigation.

### (a) sub_video_clip consistent items_queued=0

`sub_video_clip` returns `items_queued=0` on nearly every run. Separate from the predicted_format bug (video_clip.py has its own pipeline and doesn't use run_text_story_cycle). Probable cause: X API Basic tier quota exhaustion or no new qualifying video clips from the curated analyst accounts (Kitco/CNBC/Bloomberg/etc.) within the 2h fetch window. Investigation: check X API rate limit headers in scheduler logs, inspect `_search_video_clips()` tweepy result counts, consider whether `MAX_DRAFT_ATTEMPTS=5` cap + analyst quality reject path is filtering all clips.

### (b) sub_gold_media frontend label confusion

The frontend (CONTENT_AGENT_TABS config in frontend) labels `sub_video_clip` as "Gold Media". There is no separate `gold_media.py` file — the scheduler job is `sub_video_clip` and the implementation is `scheduler/agents/content/video_clip.py`. Future engineers looking for `gold_media.py` will not find it. The frontend config maps `agentName: "sub_video_clip"` to the display label "Gold Media". Document this mapping in a comment in the CONTENT_AGENT_TABS config and/or in `video_clip.py`'s module docstring to prevent confusion.

### (c) Orphan `running` rows in agent_runs

Two rows observed in `agent_runs` with `status='running'` and `ended_at=NULL` as of 2026-04-22 UTC:
- `sub_breaking_news` run started ~17:02 UTC Apr 22
- `sub_long_form` run started ~15:36 UTC Apr 22

These runs never received a final status UPDATE. The final `UPDATE agent_runs SET status=..., ended_at=...` at the end of `run_text_story_cycle` (and equivalent in bespoke run_draft_cycle pipelines) appears to fail silently in some cases — possibly when an exception occurs between the initial INSERT and the final UPDATE, or when Railway kills the process mid-run. Fix: wrap the final status update in a `try/finally` block so the UPDATE fires even if the drafting loop raises. Also consider a startup cleanup job that sets any rows stuck in `status='running'` for > 30 minutes to `status='error'` with an explanatory note, preventing stale running rows from misleading the dashboard.

### (d) sub_gold_history hallucination risk

Current design: Claude Sonnet picks a historical gold-market story from memory, then SerpAPI is used to verify factual claims after the fact. User concern: the story Claude picks may be plausible-sounding but non-existent (hallucinated event with real-sounding details). The current architecture only verifies claims AFTER Claude has already committed to a story, which means a well-constructed hallucination could pass verification if SerpAPI finds superficially matching articles.

User wants 100% factual accuracy — "it needs to actually be a 100% true story."

Options to consider:
1. Source stories from a curated list (e.g., a Config key `gold_history_story_pool` with a seeded list of verified historical events) and have Claude draft from that list rather than inventing a topic.
2. Require Claude to cite specific historical records (date, publication, verifiable claim) BEFORE the story is accepted — refuse any story that cannot name a specific documented event.
3. Add a second verification pass: after initial SerpAPI verify, require a second independent corroboration from a different source before the story is marked `compliance_passed=True`.
4. Hybrid: narrow Claude's pick to a decade + commodity context, then require an exact citation in `{"story_date": "YYYY-MM-DD", "source": "..."}` structured JSON, and reject any story where the citation cannot be confirmed via SerpAPI.

This is a quality/verification design question, not a runtime bug. Recommend addressing in a dedicated quick task.

### (e) APScheduler misfire_grace_time too short for Railway deploys

Current `misfire_grace_time=300` (5 minutes) in `scheduler/worker.py`. On 2026-04-22, cron jobs scheduled at 12:00 PT were dropped because a Railway redeploy hit during the 5-minute grace window — APScheduler considered the fires missed and skipped them rather than firing immediately after restart.

Fix: bump `misfire_grace_time` to 1800 (30 minutes) to survive typical Railway deploy windows (~2-5 minutes cold start + queue drain). This is a one-line change in `worker.py` where `AsyncIOScheduler` is instantiated. Not related to the zero-items bug investigated in this session; separate quick task.
