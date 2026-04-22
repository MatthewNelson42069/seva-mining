---
task: 260422-vxg
title: 7-sub-agent cadence rebalance + Quotes max_count=1 + Gold Media analyst quality gate
branch: quick/260422-vxg-cadence-rebalance-7-sub-agents
base: main (HEAD ddb5721 — contains m9k + mos + prior quick commits)
type: quick
atomic_commits: 1
---

<objective>
Rebalance the 7-sub-agent topology so that only Breaking News, Threads, and Long-form run on IntervalTrigger, while Quotes / Infographics / Gold Media / Gold History all run on CronTrigger. Concretely:

- Breaking News reverts from `interval_hours=1` back to `interval_hours=2` (undoes m9k's per-hour experiment).
- Threads and Long-form move from 2h → 4h.
- Quotes (already daily cron at 12:00 PT from mos) tightens `max_count` from 2 → 1.
- Infographics and Gold Media (video_clip) move from 2h interval → daily cron at 12:00 America/Los_Angeles.
- Gold History moves from 2h interval → every-other-day cron at 12:00 America/Los_Angeles (`day="*/2"`).
- Gold Media gains a drafter-level analyst/economist quality gate (mirrors the quotes.py reject-path pattern), reorders `VIDEO_ACCOUNTS` toward analyst-heavy media handles, and caps the pipeline to the first successful persist (max 1 analyst clip/day).

The `CONTENT_CRON_AGENTS` tuple shape extends from 7 fields to 5 fields (`job_id, run_fn, name, lock_id, cron_kwargs: dict`) so heterogeneous cron patterns (daily vs every-other-day) fit cleanly. `JOB_LOCK_IDS` stays identical (8 keys). No DB schema changes, no Alembic migrations, no new Config keys.

Purpose: Volume down + signal up. Current 7× every-2h firing produces too many lower-quality drafts; concentrating non-news formats at a single daily slot with tighter quality bars shifts the queue toward drafts that are genuinely worth approving.

Output: One atomic refactor commit on `quick/260422-vxg-cadence-rebalance-7-sub-agents`. NOT pushed to origin — orchestrator handles merge after user review.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@/Users/matthewnelson/seva-mining/CLAUDE.md
@/Users/matthewnelson/seva-mining/scheduler/worker.py
@/Users/matthewnelson/seva-mining/scheduler/agents/content/quotes.py
@/Users/matthewnelson/seva-mining/scheduler/agents/content/video_clip.py
@/Users/matthewnelson/seva-mining/scheduler/agents/content/breaking_news.py
@/Users/matthewnelson/seva-mining/scheduler/agents/content/gold_history.py
@/Users/matthewnelson/seva-mining/scheduler/agents/content/infographics.py
@/Users/matthewnelson/seva-mining/scheduler/tests/test_worker.py
@/Users/matthewnelson/seva-mining/scheduler/tests/test_quotes.py
@/Users/matthewnelson/seva-mining/scheduler/tests/test_video_clip.py
@/Users/matthewnelson/seva-mining/.planning/quick/260421-mos-quotes-sub-agent-daily-12pm-pacific-repu/260421-mos-PLAN.md
</context>

<interfaces>
<!-- Current CONTENT_INTERVAL_AGENTS / CONTENT_CRON_AGENTS shapes in scheduler/worker.py (pre-change) -->

```python
# scheduler/worker.py L92-100 (pre-change)
CONTENT_INTERVAL_AGENTS: list[tuple[str, object, str, int, int, int]] = [
    ("sub_breaking_news", breaking_news.run_draft_cycle,  "Breaking News",  1010,   0, 1),
    ("sub_threads",       threads.run_draft_cycle,        "Threads",        1011,  17, 2),
    ("sub_long_form",     long_form.run_draft_cycle,      "Long-form",      1012,  34, 2),
    ("sub_infographics",  infographics.run_draft_cycle,   "Infographics",   1014,  68, 2),
    ("sub_video_clip",    video_clip.run_draft_cycle,     "Gold Media",     1015,  85, 2),
    ("sub_gold_history",  gold_history.run_draft_cycle,   "Gold History",   1016, 102, 2),
]

# scheduler/worker.py L107-109 (pre-change) — 7-field tuple
CONTENT_CRON_AGENTS: list[tuple[str, object, str, int, int, int, str]] = [
    ("sub_quotes", quotes.run_draft_cycle, "Quotes", 1013, 12, 0, "America/Los_Angeles"),
]

# scheduler/worker.py L295-301 (pre-change) — cron registration loop
for job_id, run_fn, name, lock_id, hour, minute, tz in CONTENT_CRON_AGENTS:
    scheduler.add_job(
        _make_sub_agent_job(job_id, lock_id, run_fn, engine),
        trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
        id=job_id,
        name=f"{name} — daily at {hour:02d}:{minute:02d} {tz}",
    )
```

Target post-change shape (Option 2 — dict of CronTrigger kwargs):
```python
CONTENT_INTERVAL_AGENTS: list[tuple[str, object, str, int, int, int]] = [
    ("sub_breaking_news", breaking_news.run_draft_cycle,  "Breaking News",  1010,   0, 2),
    ("sub_threads",       threads.run_draft_cycle,        "Threads",        1011,  17, 4),
    ("sub_long_form",     long_form.run_draft_cycle,      "Long-form",      1012,  34, 4),
]

CONTENT_CRON_AGENTS: list[tuple[str, object, str, int, dict]] = [
    ("sub_quotes",        quotes.run_draft_cycle,       "Quotes",        1013, {"hour": 12, "minute": 0, "timezone": "America/Los_Angeles"}),
    ("sub_infographics",  infographics.run_draft_cycle, "Infographics",  1014, {"hour": 12, "minute": 0, "timezone": "America/Los_Angeles"}),
    ("sub_video_clip",    video_clip.run_draft_cycle,   "Gold Media",    1015, {"hour": 12, "minute": 0, "timezone": "America/Los_Angeles"}),
    ("sub_gold_history",  gold_history.run_draft_cycle, "Gold History",  1016, {"day": "*/2", "hour": 12, "minute": 0, "timezone": "America/Los_Angeles"}),
]

for job_id, run_fn, name, lock_id, cron_kwargs in CONTENT_CRON_AGENTS:
    scheduler.add_job(
        _make_sub_agent_job(job_id, lock_id, run_fn, engine),
        trigger=CronTrigger(**cron_kwargs),
        id=job_id,
        name=f"{name} — cron",
    )
```

Reject-path pattern to mirror in `video_clip._draft_video_caption` (from quotes.py L163-168):
```python
if parsed.get("reject") is True:
    logger.info(
        "%s: _draft_video_caption rejected — %s",
        AGENT_NAME, parsed.get("rationale", "no rationale"),
    )
    return None
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Scheduler topology rebalance + CONTENT_CRON_AGENTS dict-shape migration</name>
  <files>scheduler/worker.py</files>
  <action>
Rebalance `scheduler/worker.py` topology. One file, one logical change.

**1a. Module docstring (L1-24).** Rewrite lines ~5-11 to describe new topology:
"Post quick-260422-vxg, it starts AsyncIOScheduler with 8 jobs:
- morning_digest (daily cron, 08:00 UTC)
- 3 interval sub-agents on IntervalTrigger — sub_breaking_news every 2h, sub_threads + sub_long_form every 4h — staggered across the 4h window with offsets [0, 17, 34] minutes.
- 4 cron sub-agents — sub_quotes / sub_infographics / sub_video_clip all daily at 12:00 America/Los_Angeles; sub_gold_history every other day (`day='*/2'`) at 12:00 America/Los_Angeles."
Keep the PostgreSQL advisory lock line. Keep the Requirements line and D-12/D-13/D-14 line. Append a new history line at the end:
"quick-260422-vxg: cadence rebalance — BN reverts 1h→2h, Threads+Long-form 2h→4h, Infographics/Gold Media/Gold History moved off interval onto cron (daily noon PT, except Gold History every-other-day noon PT via `day='*/2'`). CONTENT_CRON_AGENTS tuple shape changed to (job_id, run_fn, name, lock_id, cron_kwargs: dict)."
Do NOT touch m9k's prior doc lines unrelated to this (keep lines re: prior quick IDs).

**1b. CONTENT_INTERVAL_AGENTS (L86-100).** Shrink to 3 entries and update leading comment block (L86-91).
- Replace comment block with: "Content sub-agent registration table — interval-scheduled (quick-260422-vxg). Tuple shape: (job_id, run_fn, name, lock_id, offset_minutes, interval_hours). Only 3 news-responsive agents run on interval now: sub_breaking_news every 2h, sub_threads + sub_long_form every 4h. Stagger offsets [0, 17, 34] minutes spread the three across the first 34 minutes of each hour to avoid thundering herds on SerpAPI + Anthropic. The other 4 sub-agents moved to CONTENT_CRON_AGENTS (daily / every-other-day)."
- New list:
```python
CONTENT_INTERVAL_AGENTS: list[tuple[str, object, str, int, int, int]] = [
    ("sub_breaking_news", breaking_news.run_draft_cycle,  "Breaking News",  1010,   0, 2),
    ("sub_threads",       threads.run_draft_cycle,        "Threads",        1011,  17, 4),
    ("sub_long_form",     long_form.run_draft_cycle,      "Long-form",      1012,  34, 4),
]
```
Remove the `# sub_quotes moved to CONTENT_CRON_AGENTS` comment line — it's stale now that sub_infographics, sub_video_clip, sub_gold_history are ALSO cron-scheduled.

**1c. CONTENT_CRON_AGENTS (L102-109).** Extend to 4 entries with dict-shape.
- Replace comment block (L102-106) with: "Cron-scheduled sub-agents (quick-260422-vxg). Tuple shape: (job_id, run_fn, name, lock_id, cron_kwargs: dict). `cron_kwargs` is unpacked directly into `CronTrigger(**cron_kwargs)` at registration time so heterogeneous patterns (daily noon PT vs every-other-day noon PT via `day='*/2'`) coexist without extra tuple columns. All 4 agents fire at 12:00 America/Los_Angeles — post US morning news, pre market close. Gold History fires every other day because the used-topics guard means most daily ticks no-op; halving cadence halves the Claude picker spend."
- New list (exact shape shown in `<interfaces>` block above). Keep lock IDs 1013/1014/1015/1016.

**1d. CronTrigger registration loop (L295-301).** Update to unpack 5 fields and call `CronTrigger(**cron_kwargs)`.
```python
for job_id, run_fn, name, lock_id, cron_kwargs in CONTENT_CRON_AGENTS:
    scheduler.add_job(
        _make_sub_agent_job(job_id, lock_id, run_fn, engine),
        trigger=CronTrigger(**cron_kwargs),
        id=job_id,
        name=f"{name} — cron ({' '.join(f'{k}={v}' for k, v in cron_kwargs.items())})",
    )
```
(The descriptive `name` string uses the cron_kwargs dict so Railway logs / APScheduler job listings still show the pattern for each job.)

**1e. Startup log line (L260-263).** Update to match new topology:
```python
logger.info(
    "Schedule config: digest=cron(%d:00 UTC), interval_sub_agents=%d jobs (sub_breaking_news=2h, sub_threads=4h, sub_long_form=4h), cron_sub_agents=%d jobs (3× daily 12:00 America/Los_Angeles + 1× every-other-day 12:00 America/Los_Angeles via day='*/2')",
    digest_hour, len(CONTENT_INTERVAL_AGENTS), len(CONTENT_CRON_AGENTS),
)
```

**1f. build_scheduler docstring (L246-255).** Refresh to describe new topology:
"Build the APScheduler instance with 8 jobs registered.

- morning_digest: cron at morning_digest_schedule_hour (default 08:00 UTC).
- 3 interval sub-agents: IntervalTrigger with per-agent hours (sub_breaking_news=2, sub_threads=4, sub_long_form=4) and staggered start_date offsets [0, 17, 34] minutes.
- 4 cron sub-agents: sub_quotes / sub_infographics / sub_video_clip daily at 12:00 America/Los_Angeles; sub_gold_history every other day at 12:00 America/Los_Angeles.

Config keys:
- morning_digest_schedule_hour (default: 8)"

**1g. Sanity-preserve m9k's 10s buffer for offset=0 (L283-287).** Keep the `+10s` buffer logic exactly — still matters for Breaking News (offset=0).

**DO NOT CHANGE:**
- `JOB_LOCK_IDS` dict (L74-83) — all 8 keys + integer IDs unchanged.
- `with_advisory_lock`, `_make_morning_digest_job`, `_make_sub_agent_job`, `_read_schedule_config`, `upsert_agent_config`, `_validate_env`, `main` — untouched.
- morning_digest registration block (L274-281) — untouched.
- Interval loop field unpacking (L284) stays `for job_id, run_fn, name, lock_id, offset, interval_hours in CONTENT_INTERVAL_AGENTS:` — same 6-tuple shape.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler &amp;&amp; uv run ruff check worker.py</automated>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler &amp;&amp; grep -n 'interval_hours=\|interval_hours: \|", 1010, \|", 1011, \|", 1012, \|"day": "\*/2"\|cron_kwargs\|CronTrigger(\*\*cron_kwargs)' worker.py</automated>
  </verify>
  <done>
- `grep -n 'sub_breaking_news.*1010.*0, 2\|"Breaking News".*1010, *0, 2' worker.py` matches (BN reverted to 2h).
- `grep -n 'sub_threads.*1011.*17, 4' worker.py` matches (Threads at 4h).
- `grep -n 'sub_long_form.*1012.*34, 4' worker.py` matches (Long-form at 4h).
- `len(CONTENT_INTERVAL_AGENTS) == 3` when imported in a Python shell.
- `len(CONTENT_CRON_AGENTS) == 4` and each 5th element is a dict.
- `grep -c '"day": "\*/2"' worker.py` returns 1 (Gold History only).
- `uv run ruff check worker.py` clean.
  </done>
</task>

<task type="auto">
  <name>Task 2: Sub-agent docstring sync (breaking_news, gold_history, + optional threads/long_form/infographics/video_clip/quotes)</name>
  <files>scheduler/agents/content/breaking_news.py, scheduler/agents/content/gold_history.py, scheduler/agents/content/threads.py, scheduler/agents/content/long_form.py, scheduler/agents/content/infographics.py, scheduler/agents/content/video_clip.py, scheduler/agents/content/quotes.py</files>
  <action>
Sync sub-agent docstrings to the new cadence. Most files are touched only if the docstring literally states a cadence — grep first, skip files that don't mention cadence.

**2a. `scheduler/agents/content/breaking_news.py` L3 (REQUIRED):** Change "Runs every hour on its own APScheduler cron." → "Runs every 2 hours on its own APScheduler cron (reverted from m9k's 1h experiment in quick-260422-vxg — 1h was producing too much duplicate-story churn for the upside in urgency)." This undoes m9k's docstring change.

**2b. `scheduler/agents/content/gold_history.py` L11-12 (REQUIRED):** Change "Runs on the standard 2h sub-agent cadence; most ticks no-op because the used-topics guard skips already-surfaced stories." → "Runs every other day at 12:00 America/Los_Angeles via CronTrigger(day='*/2', hour=12, minute=0, timezone='America/Los_Angeles') (quick-260422-vxg). Most runs still no-op when `_pick_story` returns an already-used slug; halving cadence halves the Claude picker spend."

**2c. `scheduler/agents/content/threads.py` (CONDITIONAL):** Grep for `"2h"` or `"every 2 hour"`. If found in the module docstring, change to `"4h"` or `"every 4 hours"`. If not found, leave file alone. Do NOT touch `_draft` / `run_draft_cycle` bodies.

**2d. `scheduler/agents/content/long_form.py` (CONDITIONAL):** Same rule as threads.py — only update cadence strings in docstring if present.

**2e. `scheduler/agents/content/infographics.py` (CONDITIONAL):** Grep for `"2h"` or `"every 2 hour"`. If found, change to `"daily at 12:00 America/Los_Angeles"`. Otherwise leave alone. The `_draft` prompt body and `run_draft_cycle` body must NOT be touched.

**2f. `scheduler/agents/content/video_clip.py` (CONDITIONAL on docstring only — content changes happen in Task 3):** Grep for `"2h"` or `"every 2 hour"` in module-level docstring. If present, change to `"daily at 12:00 America/Los_Angeles"`. Task 3 will make the substantive body changes; this sub-task only covers the cadence line if it exists in the docstring.

**2g. `scheduler/agents/content/quotes.py` (CONDITIONAL):** Grep for `"max_count=2"` or `"top-2"` in docstrings. Update to `max_count=1` / `top-1`. (The actual `max_count=1` code change happens in Task 3.) Also update line 195 `run_draft_cycle` docstring "fetch → filter → reputable-only → top-2 → draft" → "fetch → filter → reputable-only → top-1 → draft".

Docstring-only edits — no behavioral change in this task.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler &amp;&amp; grep -n 'Runs every 2 hours\|quick-260422-vxg' agents/content/breaking_news.py agents/content/gold_history.py</automated>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler &amp;&amp; grep -n 'top-2\|top-1' agents/content/quotes.py</automated>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler &amp;&amp; uv run ruff check agents/content/</automated>
  </verify>
  <done>
- breaking_news.py L3 says "Runs every 2 hours" and mentions vxg reversal.
- gold_history.py L11-12 describes the `day="*/2"` cron pattern and references quick-260422-vxg.
- quotes.py `run_draft_cycle` docstring says "top-1" (not "top-2").
- Any conditional files that mentioned "2h" now mention "4h" (threads/long_form) or "daily at 12:00 America/Los_Angeles" (infographics/video_clip).
- `uv run ruff check agents/content/` clean.
  </done>
</task>

<task type="auto">
  <name>Task 3: Quotes max_count=1 + Gold Media (video_clip) analyst quality gate, account reorder, first-persist break</name>
  <files>scheduler/agents/content/quotes.py, scheduler/agents/content/video_clip.py</files>
  <action>
Two files, three distinct changes.

**3a. `scheduler/agents/content/quotes.py` L200:** Change `max_count=2` → `max_count=1`. This is a single-line kwarg swap inside `run_draft_cycle`. The `run_text_story_cycle` signature already accepts `max_count` (verified from mos) so no other change needed. (Docstring update was handled in Task 2g; verify it's consistent.)

**3b. `scheduler/agents/content/video_clip.py` L41-49 — reorder VIDEO_ACCOUNTS.** Replace the existing list with an analyst/economist-media-heavy order. Keep the list at 7 entries so the `[:5]` slice at L91 still picks the top 5 highest-signal handles:

```python
VIDEO_ACCOUNTS = [
    "Kitco",            # Michael Oliver / Jeff Christian / roundtable analyst interviews
    "CNBC",             # Halftime Report, Fast Money — frequent analyst segments
    "Bloomberg",        # analyst + economist segments
    "BloombergTV",      # real-time analyst interviews
    "ReutersBiz",       # economist panels
    "FT",               # Financial Times video interviews
    "MarketWatch",      # analyst segments
]
```

Dropped (no longer in list): BarrickGold, WorldGoldCouncil, Mining, Newaborngold — all company/sector handles that posted PR-style clips rather than analyst commentary. Rationale for the reorder: the goal is to surface *analyst/economist interpretation* of gold moves, not corporate announcements or amateur sector content.

Update the comment on L39-40 to reflect reorder: "Curated video-source accounts (CONT-09, CONT-13). Reordered + trimmed in quick-260422-vxg to favor analyst/economist media handles over corporate/sector accounts — Gold Media's goal is senior-analyst commentary, not PR clips."

**3c. `scheduler/agents/content/video_clip.py` L154-213 — add drafter quality gate in `_draft_video_caption`.** Mirror the quotes.py reject-path pattern exactly.

Update the `system_prompt` to describe the quality bar (extend the existing 5-line prompt):
```python
system_prompt = (
    f"{snapshot_block}\n\n"
    "You are a senior gold market analyst. You write quote-tweet style captions "
    "for video clips from gold sector figures. Write 1-3 sentences: who said it, "
    "what the key claim is, why it matters to gold investors. Lead with the data "
    "or the insight — not preamble. Also provide an Instagram-adapted version "
    "(same content, slightly more context for a less technical audience). "
    "You never mention Seva Mining. You never give financial advice."
)
```
(Keep system_prompt mostly identical — quality bar belongs in user_prompt next to the data.)

Replace `user_prompt` body with the existing caption-ask PLUS a reject path and a quality bar. New `user_prompt`:
```python
user_prompt = f"""Write a caption for this video clip from @{author_username} ({author_name}).

Tweet text: {tweet_text}
Video URL: {tweet_url}

## Quality bar — draft ONLY if the video features an identifiable senior
analyst or economist with clear gold-market commentary:
1. **Speaker identifiable:** Named analyst, economist, strategist, or
   central bank official — NOT anonymous reporters reading headlines, NOT
   retail commentators, NOT pure market-recap voice-overs without named
   speaker.
2. **Substantive commentary:** Contains an analyst view, forecast, data
   interpretation, or contrarian take on gold price / macro. NOT just
   "gold prices rose today" news-recital.
3. **Gold focus:** Speaker discusses gold specifically (not mentioning
   gold in passing during a broader markets segment).

If the video does NOT meet this bar, respond with:
{{"reject": true, "rationale": "1-2 sentence reason"}}

Otherwise, respond in valid JSON:
{{
  "twitter_caption": "1-3 sentences for X quote-tweet (data-forward, senior analyst voice)",
  "instagram_caption": "same content adapted for Instagram (slightly more context)"
}}"""
```

After `parsed = json.loads(raw)` (around L202), insert reject handling before the return dict (mirrors quotes.py L163-168):
```python
if parsed.get("reject") is True:
    logger.info(
        "%s: _draft_video_caption rejected — %s",
        AGENT_NAME, parsed.get("rationale", "no rationale given"),
    )
    return None
```
The existing success-path return dict (L207-213) stays unchanged.

**3d. `scheduler/agents/content/video_clip.py` L260-317 — cap to first successful persist + MAX_DRAFT_ATTEMPTS.** Two insertions inside `run_draft_cycle`:

First, immediately after `clips = await _search_video_clips(session, tweepy_client)` on L252 and before the `if not clips:` check on L254, sort + cap:
```python
clips.sort(key=lambda c: c.get("created_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
MAX_DRAFT_ATTEMPTS = 5
clips = clips[:MAX_DRAFT_ATTEMPTS]
```
(Use `datetime.min.replace(tzinfo=timezone.utc)` to keep datetime-aware — `tweet.created_at` from tweepy is tz-aware.)

Second, inside the `if compliance_ok:` block (L301-307), add a `break` after the log line:
```python
if compliance_ok:
    rationale = f"Video clip from @{clip['author_username']} on gold sector"
    item = content_agent.build_draft_item(bundle, rationale)
    session.add(item)
    await session.flush()
    items_queued += 1
    logger.info("%s: queued video clip from @%s", AGENT_NAME, clip["author_username"])
    break  # max 1 analyst clip per day — per quick-260422-vxg
```

Also update `run_draft_cycle` docstring (L217-220) to mention the new behavior: append a final sentence to the existing docstring:
"Post quick-260422-vxg: iterates up to MAX_DRAFT_ATTEMPTS=5 most-recent candidates, breaks after first successful persist — goal is 1 analyst clip/day. If no clip passes the drafter quality bar, none queued."

**DO NOT CHANGE:**
- quotes.py `_draft` body, `REPUTABLE_SOURCES`, system_prompt, user_prompt — all stay.
- video_clip.py `_search_video_clips` body (the X API quota check + query + media filter) — unchanged.
- video_clip.py `_get_config` / `_set_config_str` helpers — unchanged.
- video_clip.py `AgentRun` / `ContentBundle` writing logic surrounding the loop — unchanged except for the break and the top-of-loop clips-trim.
- The `accounts_clause = " OR ".join(f"from:{acct}" for acct in VIDEO_ACCOUNTS[:5])` line on L91 stays as-is — the reorder naturally promotes the top 5 analyst-heavy handles without changing the slice arithmetic.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler &amp;&amp; grep -n 'max_count=1' agents/content/quotes.py</automated>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler &amp;&amp; grep -n 'reject\|MAX_DRAFT_ATTEMPTS\|break  # max 1\|BloombergTV\|ReutersBiz' agents/content/video_clip.py</automated>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler &amp;&amp; uv run ruff check agents/content/quotes.py agents/content/video_clip.py</automated>
  </verify>
  <done>
- `grep -c 'max_count=1' agents/content/quotes.py` returns exactly 1 (run_draft_cycle call site).
- `grep -c 'max_count=2' agents/content/quotes.py` returns 0.
- `grep -c 'reject' agents/content/video_clip.py` returns ≥2 (prompt body + parsed-dict check).
- `grep -c 'MAX_DRAFT_ATTEMPTS' agents/content/video_clip.py` returns ≥1.
- `grep -c 'break  # max 1' agents/content/video_clip.py` returns 1.
- `VIDEO_ACCOUNTS[:3] == ["Kitco", "CNBC", "Bloomberg"]` (verified by import).
- `"BarrickGold" not in VIDEO_ACCOUNTS` (verified by import).
- `uv run ruff check` clean on both files.
  </done>
</task>

<task type="auto">
  <name>Task 4: Test updates — worker + quotes + video_clip (rescope + add new coverage)</name>
  <files>scheduler/tests/test_worker.py, scheduler/tests/test_quotes.py, scheduler/tests/test_video_clip.py</files>
  <action>
Update tests to match the new topology and behavior. No new test files — append/edit existing ones.

**4a. `scheduler/tests/test_worker.py` rescopes:**

- L74-80 `test_sub_agents_total_seven`: Change the body asserts from `(CONTENT_INTERVAL_AGENTS) == 6` and `(CONTENT_CRON_AGENTS) == 1` to `(CONTENT_INTERVAL_AGENTS) == 3` and `(CONTENT_CRON_AGENTS) == 4`. Top-level `sum == 7` assertion stays. Docstring: "Interval + cron sub-agent lists together must still cover all 7 sub-agents (post-vxg: 3 interval + 4 cron)."

- L83-86 `test_sub_agent_staggering`: Trim the expected offsets list to `[0, 17, 34]`. Update docstring: "Post quick-260422-vxg: only 3 interval agents remain. Offsets are [0, 17, 34] minutes — Breaking News (2h), Threads + Long-form (4h each)."

- L89-105 `test_sub_agent_lock_ids`: Update the `CONTENT_CRON_AGENTS` iteration for the new 5-field tuple shape. Replace:
  ```python
  for job_id, _, _, lock_id, *_ in CONTENT_CRON_AGENTS:
      sub_entries[job_id] = lock_id
  ```
  with the same pattern — `*_` unpacking is already tolerant of the new shape (5 fields instead of 7). No test body change needed here; the assertion dict still contains all 7 sub-agent lock IDs. Confirm by re-running.

- L108-117 `test_quotes_is_daily_cron`: Update to match the new dict-shape:
  ```python
  def test_quotes_is_daily_cron():
      """sub_quotes is registered as a cron sub-agent at 12:00 America/Los_Angeles (dict-shape post-vxg)."""
      quotes_entry = next(t for t in CONTENT_CRON_AGENTS if t[0] == "sub_quotes")
      assert quotes_entry[0] == "sub_quotes"
      assert quotes_entry[2] == "Quotes"
      assert quotes_entry[3] == 1013
      assert quotes_entry[4] == {"hour": 12, "minute": 0, "timezone": "America/Los_Angeles"}
  ```
  (Tuple-index lookup instead of `CONTENT_CRON_AGENTS[0]` — now 4 entries, not 1.)

- L120-132 `test_retired_crons_absent_from_job_lock_ids`: Unchanged (JOB_LOCK_IDS still has 8 keys).

- L135-155 `test_scheduler_registers_8_jobs`: Unchanged (still 8 jobs total: morning_digest + 7 sub-agents).

- L158-167 `test_read_schedule_config_has_no_retired_keys`: Unchanged.

**4b. `scheduler/tests/test_worker.py` new tests (append to end of file):**

```python
def test_interval_agents_cadences():
    """Post-vxg interval cadences: BN=2h, Threads=4h, Long-form=4h."""
    cadences = {t[0]: t[5] for t in CONTENT_INTERVAL_AGENTS}
    assert cadences == {
        "sub_breaking_news": 2,
        "sub_threads":       4,
        "sub_long_form":     4,
    }


def test_cron_agents_count_four():
    """Post-vxg: 4 cron sub-agents (quotes / infographics / video_clip / gold_history)."""
    assert len(CONTENT_CRON_AGENTS) == 4
    ids = [t[0] for t in CONTENT_CRON_AGENTS]
    assert set(ids) == {
        "sub_quotes", "sub_infographics", "sub_video_clip", "sub_gold_history",
    }


def test_cron_agents_use_dict_shape():
    """Post-vxg: 5th tuple element is a CronTrigger kwargs dict."""
    for entry in CONTENT_CRON_AGENTS:
        assert len(entry) == 5
        assert isinstance(entry[4], dict)
        # All four fire at noon Pacific.
        assert entry[4]["hour"] == 12
        assert entry[4]["minute"] == 0
        assert entry[4]["timezone"] == "America/Los_Angeles"


def test_gold_history_is_every_other_day():
    """sub_gold_history uses day='*/2' so it fires every other day at noon PT."""
    entry = next(t for t in CONTENT_CRON_AGENTS if t[0] == "sub_gold_history")
    assert entry[3] == 1016
    assert entry[4] == {
        "day": "*/2",
        "hour": 12,
        "minute": 0,
        "timezone": "America/Los_Angeles",
    }


def test_infographics_is_daily_cron():
    entry = next(t for t in CONTENT_CRON_AGENTS if t[0] == "sub_infographics")
    assert entry[3] == 1014
    assert entry[4] == {"hour": 12, "minute": 0, "timezone": "America/Los_Angeles"}


def test_video_clip_is_daily_cron():
    entry = next(t for t in CONTENT_CRON_AGENTS if t[0] == "sub_video_clip")
    assert entry[3] == 1015
    assert entry[4] == {"hour": 12, "minute": 0, "timezone": "America/Los_Angeles"}
```

**4c. `scheduler/tests/test_quotes.py` L112-123 `test_run_draft_cycle_passes_filters`:** Update line 121 assertion from `kwargs["max_count"] == 2` → `kwargs["max_count"] == 1`. No other change in that test.

**4d. `scheduler/tests/test_video_clip.py` — append two new tests:**

```python
def test_video_accounts_reordered_analyst_first():
    """VIDEO_ACCOUNTS is reordered post-vxg to favor analyst/economist media handles.

    Top 3 must be Kitco / CNBC / Bloomberg (analyst-interview-heavy).
    Corporate/sector accounts (BarrickGold, WorldGoldCouncil, Mining, Newaborngold)
    must be dropped — they posted PR-style clips, not analyst commentary.
    """
    assert video_clip.VIDEO_ACCOUNTS[:3] == ["Kitco", "CNBC", "Bloomberg"]
    assert "BarrickGold" not in video_clip.VIDEO_ACCOUNTS
    assert "WorldGoldCouncil" not in video_clip.VIDEO_ACCOUNTS
    assert "Mining" not in video_clip.VIDEO_ACCOUNTS
    assert "Newaborngold" not in video_clip.VIDEO_ACCOUNTS
    # New additions — analyst-heavy handles.
    assert "BloombergTV" in video_clip.VIDEO_ACCOUNTS
    assert "ReutersBiz" in video_clip.VIDEO_ACCOUNTS


@pytest.mark.asyncio
async def test_draft_video_caption_returns_none_on_reject(caplog):
    """_draft_video_caption returns None when Claude responds with {"reject": true, ...}."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text='{"reject": true, "rationale": "anonymous voice-over, no named speaker"}')]
    client.messages.create = AsyncMock(return_value=response)

    with caplog.at_level("INFO"):
        draft = await video_clip._draft_video_caption(
            tweet_text="Gold prices rose today.",
            author_username="Kitco",
            author_name="Kitco News",
            tweet_url="https://twitter.com/Kitco/status/1",
            market_snapshot=None,
            client=client,
        )
    assert draft is None
    assert "rejected" in caplog.text
    assert "anonymous" in caplog.text
```

**DO NOT CHANGE:**
- Existing `test_draft_video_caption_returns_expected_shape` (L61-81) — still passes because non-reject JSON hits the existing success-path.
- Existing `test_draft_video_caption_returns_none_on_parse_failure` (L83-94) — still passes (invalid JSON hits the try/except).
- `test_search_video_clips_respects_quota_cap` — unchanged, still valid.
- `test_module_surface` (test_video_clip.py L31-39) — already asserts `"Kitco" in VIDEO_ACCOUNTS` and Kitco is still first. Unchanged.
- `test_reputable_sources_set_populated`, `test_draft_returns_draft_content_shape`, `test_draft_returns_none_on_reject`, `test_draft_returns_none_on_json_parse_failure`, `test_run_draft_cycle_no_candidates_exits_cleanly` in test_quotes.py — all unchanged.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler &amp;&amp; uv run ruff check tests/test_worker.py tests/test_quotes.py tests/test_video_clip.py</automated>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler &amp;&amp; uv run pytest tests/test_worker.py tests/test_quotes.py tests/test_video_clip.py -x -v</automated>
  </verify>
  <done>
- `uv run pytest tests/test_worker.py -v` shows `test_sub_agents_total_seven`, `test_sub_agent_staggering`, `test_sub_agent_lock_ids`, `test_quotes_is_daily_cron`, `test_retired_crons_absent_from_job_lock_ids`, `test_scheduler_registers_8_jobs`, `test_read_schedule_config_has_no_retired_keys` PASSING, PLUS new tests `test_interval_agents_cadences`, `test_cron_agents_count_four`, `test_cron_agents_use_dict_shape`, `test_gold_history_is_every_other_day`, `test_infographics_is_daily_cron`, `test_video_clip_is_daily_cron` PASSING.
- `uv run pytest tests/test_quotes.py -v` shows all 7 tests pass including updated `test_run_draft_cycle_passes_filters` with `max_count == 1`.
- `uv run pytest tests/test_video_clip.py -v` shows all 5 existing tests + 2 new tests (`test_video_accounts_reordered_analyst_first`, `test_draft_video_caption_returns_none_on_reject`) PASSING.
  </done>
</task>

<task type="auto">
  <name>Task 5: Full scheduler test suite + ruff + commit</name>
  <files>N/A (runs tests + commit only)</files>
  <action>
Final verification + single atomic commit.

**5a. Full ruff on scheduler/:**
```bash
cd /Users/matthewnelson/seva-mining/scheduler && uv run ruff check .
```
Fix any reported issues before proceeding. Expected: clean.

**5b. Full pytest on scheduler/:**
```bash
cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest -x
```
Expected: all green. Test count should be ≥87 (baseline from mos was 82; vxg adds at minimum: 6 new worker tests + 2 new video_clip tests = 8 new; 3 tests rescoped in place — not counted as new). If the count is lower, investigate; rescoped tests might have been deleted instead of edited.

**5c. git status sanity check:**
```bash
git -C /Users/matthewnelson/seva-mining status --short
```
Expected changed files (exact list):
- scheduler/worker.py
- scheduler/agents/content/quotes.py
- scheduler/agents/content/video_clip.py
- scheduler/agents/content/breaking_news.py
- scheduler/agents/content/gold_history.py
- scheduler/tests/test_worker.py
- scheduler/tests/test_quotes.py
- scheduler/tests/test_video_clip.py
- (optional, only if grep-conditional hit) scheduler/agents/content/threads.py
- (optional) scheduler/agents/content/long_form.py
- (optional) scheduler/agents/content/infographics.py

NO other files should show as changed. If unexpected files appear (especially from the `scheduler/agents/content/__init__.py`, `scheduler/agents/content_agent.py`, or any Alembic/migration path), stop and investigate — this task is strictly schedule-shape + drafter-bar.

**5d. git diff sanity check:**
```bash
git -C /Users/matthewnelson/seva-mining diff --stat
```
Visually scan the diff stat. Reasonable expectations: worker.py ~40-60 lines changed, video_clip.py ~40-80 lines changed, quotes.py ~2-5 lines changed, breaking_news.py ~1-3 lines changed, gold_history.py ~2-5 lines changed, test_worker.py ~60-100 lines added/changed, test_quotes.py ~1 line changed, test_video_clip.py ~30-50 lines added.

**5e. Atomic commit:**
```bash
git -C /Users/matthewnelson/seva-mining add \
  scheduler/worker.py \
  scheduler/agents/content/quotes.py \
  scheduler/agents/content/video_clip.py \
  scheduler/agents/content/breaking_news.py \
  scheduler/agents/content/gold_history.py \
  scheduler/tests/test_worker.py \
  scheduler/tests/test_quotes.py \
  scheduler/tests/test_video_clip.py
# Also add any Task 2c/2d/2e/2f conditionally-updated files if they show in git status:
git -C /Users/matthewnelson/seva-mining add scheduler/agents/content/threads.py 2>/dev/null || true
git -C /Users/matthewnelson/seva-mining add scheduler/agents/content/long_form.py 2>/dev/null || true
git -C /Users/matthewnelson/seva-mining add scheduler/agents/content/infographics.py 2>/dev/null || true

git -C /Users/matthewnelson/seva-mining commit -m "$(cat <<'EOF'
refactor(scheduler): 7-sub-agent cadence rebalance + quotes max=1 + gold media analyst bar (quick-260422-vxg)

Rebalance sub-agent topology — 3 interval + 4 cron instead of prior 6 interval + 1 cron:

Interval (IntervalTrigger):
- sub_breaking_news: 1h → 2h (reverts m9k 1h experiment; too much churn)
- sub_threads: 2h → 4h
- sub_long_form: 2h → 4h
- Stagger offsets trimmed to [0, 17, 34] minutes

Cron (CronTrigger, 12:00 America/Los_Angeles):
- sub_quotes: daily (unchanged from mos)
- sub_infographics: moved from interval(2h) → daily cron
- sub_video_clip: moved from interval(2h) → daily cron
- sub_gold_history: moved from interval(2h) → every other day via day="*/2"

CONTENT_CRON_AGENTS tuple shape changed from 7 fields to 5 fields — the
5th field is now a CronTrigger kwargs dict so heterogeneous cron patterns
(daily vs every-other-day) coexist cleanly:
    (job_id, run_fn, name, lock_id, cron_kwargs: dict)

Quotes tightening:
- max_count: 2 → 1 (surface only the single highest-signal reputable quote/day)

Gold Media (video_clip) quality gate:
- Drafter-level analyst/economist quality bar in _draft_video_caption
  (mirrors quotes.py reject-path pattern) — returns None for anonymous
  voice-overs / pure news recital / off-gold segments
- VIDEO_ACCOUNTS reordered + trimmed: analyst-interview-heavy media
  (Kitco, CNBC, Bloomberg, BloombergTV, ReutersBiz, FT, MarketWatch);
  dropped corporate/sector accounts (BarrickGold, WorldGoldCouncil,
  Mining, Newaborngold) that were PR-sourced, not analyst commentary
- run_draft_cycle caps to first successful persist (break after items_queued++)
  and iterates MAX_DRAFT_ATTEMPTS=5 most-recent candidates — goal is 1
  analyst clip/day; if none passes the bar, none queued

No DB schema changes. No Alembic migrations. No new Config keys. JOB_LOCK_IDS
(8 keys) unchanged. Interval loop unpacking shape unchanged.

Tests:
- test_worker.py: rescoped test_sub_agents_total_seven (now 3+4),
  test_sub_agent_staggering (now [0,17,34]), test_quotes_is_daily_cron
  (dict-shape lookup); added test_interval_agents_cadences,
  test_cron_agents_count_four, test_cron_agents_use_dict_shape,
  test_gold_history_is_every_other_day, test_infographics_is_daily_cron,
  test_video_clip_is_daily_cron
- test_quotes.py: test_run_draft_cycle_passes_filters asserts max_count=1
- test_video_clip.py: added test_video_accounts_reordered_analyst_first and
  test_draft_video_caption_returns_none_on_reject
EOF
)"
```

**5f. Post-commit verification:**
```bash
git -C /Users/matthewnelson/seva-mining log -1 --stat
git -C /Users/matthewnelson/seva-mining status --short
```
Expected: log shows one new commit on `quick/260422-vxg-cadence-rebalance-7-sub-agents`; status is clean.

**DO NOT push to origin.** Orchestrator handles merge + push after user review. Stop after the local commit.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler &amp;&amp; uv run ruff check .</automated>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler &amp;&amp; uv run pytest -x</automated>
    <automated>git -C /Users/matthewnelson/seva-mining log -1 --format='%s' | grep -q 'quick-260422-vxg'</automated>
  </verify>
  <done>
- `uv run ruff check .` returns 0 (clean) across entire scheduler/ tree.
- `uv run pytest -x` returns 0 with test count ≥87 (baseline 82 + at least 8 net new). All green.
- `git log -1 --format='%s'` shows the refactor commit subject.
- `git status --short` shows clean working tree.
- Branch is still `quick/260422-vxg-cadence-rebalance-7-sub-agents`. Not pushed.
  </done>
</task>

</tasks>

<verification>
**Enumerated validation criteria (all must pass):**

1. `grep -n 'interval_hours=\|1010, *0, 2\|1011, *17, 4\|1012, *34, 4' scheduler/worker.py` — BN row shows 2h, Threads + Long-form show 4h.
2. `grep -c 'CONTENT_INTERVAL_AGENTS' scheduler/worker.py` ≥ 2 (definition + loop).
3. `grep -c 'CONTENT_CRON_AGENTS' scheduler/worker.py` ≥ 2 (definition + loop).
4. `grep -n 'sub_gold_history' scheduler/worker.py` — appears in CONTENT_CRON_AGENTS, NOT CONTENT_INTERVAL_AGENTS.
5. `grep -n 'sub_infographics\|sub_video_clip' scheduler/worker.py` — both in CONTENT_CRON_AGENTS, NOT CONTENT_INTERVAL_AGENTS.
6. `grep -c '"day": "\*/2"' scheduler/worker.py` = 1 (gold_history cron_kwargs).
7. `grep -c 'max_count=1' scheduler/agents/content/quotes.py` = 1 (run_draft_cycle).
8. `grep -c 'max_count=2' scheduler/agents/content/quotes.py` = 0.
9. `grep -c 'reject' scheduler/agents/content/video_clip.py` ≥ 2 (prompt body + parsed-dict check).
10. `grep -c 'MAX_DRAFT_ATTEMPTS' scheduler/agents/content/video_clip.py` ≥ 1.
11. `grep -c 'break  # max 1' scheduler/agents/content/video_clip.py` = 1.
12. `grep -c 'BarrickGold\|WorldGoldCouncil\|Newaborngold' scheduler/agents/content/video_clip.py` = 0.
13. `grep -c 'BloombergTV\|ReutersBiz' scheduler/agents/content/video_clip.py` ≥ 2.
14. `cd scheduler && uv run ruff check .` clean.
15. `cd scheduler && uv run pytest -x` green, test count ≥ 87.
16. `git log -1 --format='%s'` shows the vxg refactor subject; branch = `quick/260422-vxg-cadence-rebalance-7-sub-agents`; NOT pushed.
</verification>

<success_criteria>
- Single atomic commit on `quick/260422-vxg-cadence-rebalance-7-sub-agents` with the subject `refactor(scheduler): 7-sub-agent cadence rebalance + quotes max=1 + gold media analyst bar (quick-260422-vxg)`.
- 8 scheduled jobs register (morning_digest + 3 interval + 4 cron sub-agents). JOB_LOCK_IDS still has 8 keys with unchanged IDs.
- `CONTENT_CRON_AGENTS` is a list of 5-tuples with dict-shaped cron_kwargs; `CONTENT_INTERVAL_AGENTS` is a list of 3 6-tuples.
- `_draft_video_caption` returns `None` on `{"reject": true, ...}` response (logged with rationale).
- `run_draft_cycle` in video_clip iterates at most 5 most-recent candidates and breaks after first successful persist.
- `quotes.run_draft_cycle` calls `run_text_story_cycle(max_count=1, source_whitelist=REPUTABLE_SOURCES, ...)`.
- No files outside scheduler/ and its tests/ are modified.
- No DB schema / Alembic / Config changes.
</success_criteria>

<constraints>
- **ONE atomic commit.** Do NOT break this into multiple commits on the branch — the orchestrator merge expects a single squashable commit.
- **Do NOT push to origin.** User reviews locally; orchestrator handles merge + push.
- **No DB schema changes.** No Alembic migrations. No new Config keys.
- **Zero changes to:** `scheduler/agents/content/__init__.py` (`run_text_story_cycle` stays exactly as mos left it — max_count + source_whitelist kwargs are already plumbed). `scheduler/agents/content_agent.py` (library module — untouched). `scheduler/agents/content/infographics.py` _draft body (only docstring if cadence literal present). `scheduler/agents/content/gold_history.py` drafter/picker bodies (only docstring).
- **m9k 10s offset-0 buffer stays.** Still matters for Breaking News (still offset=0 in the new 3-interval topology).
- **JOB_LOCK_IDS unchanged.** All 8 keys + integer IDs (1005, 1010-1016) must remain identical.
- **Tuple-shape migration is one-shot.** Both the `CONTENT_CRON_AGENTS` definition and the cron registration loop in `build_scheduler` must change in the same edit — leaving one in the old shape will crash at startup.
- **Reject-path mirror exact.** `video_clip._draft_video_caption` reject logging format should match `quotes._draft`'s exactly (same `%s: ...` placeholder style + `no rationale given` default). This keeps grep-ability consistent across reject events in Railway logs.
- **No scope creep:** The infographics historical-fallback drafter explicitly called out as deferred follow-up — do NOT add a `_pick_historical_infographic_topic` / `infographics_used_topics` / `_draft_historical_infographic` / decision-branch body here. Flag in SUMMARY + STATE.md only.
- **Frontend untouched.** No `frontend/` changes. `draft_items.platform` stays `String(20)`, `Platform` type stays `'content'` only.
</constraints>

<deferred>
**Infographics "historical fallback" drafter** — user directive says "If can't link to news, create interesting historical infographics." Current `run_draft_cycle` only drafts when SerpAPI returns stories with `predicted_format="infographic"`; if the daily noon cron fetches 0 matches, zero bundles queue. A future quick task will add:
- New `_pick_historical_infographic_topic(used_topics)` Claude picker in `scheduler/agents/content/infographics.py`
- New `infographics_used_topics` Config key for dedup (mirrors `gold_history_used_topics`)
- New `_draft_historical_infographic` drafter prompt for timeless gold-data infographics (central bank reserves over time, historical bull runs, M&A waves, etc.)
- Decision branch in `run_draft_cycle`: if news-path queued <2, run historical-fallback path for the remainder
- Architecture mirrors `gold_history.py` (picker + dedup + drafter + review + bundle write). Flag in 260422-vxg SUMMARY and STATE.md so it stays visible for the next quick-task batch.

Rationale for deferring: It doubles this task's surface area (new picker + new Config key + new drafter + new dedup + new tests) and delays the queue-volume reduction the user wants now. The fallback can ship as `quick-26042X-NEXTID-infographics-historical-fallback` once vxg lands.
</deferred>

<output>
After completion, write SUMMARY to:
`.planning/quick/260422-vxg-multi-agent-cadence-rebalance/260422-vxg-SUMMARY.md`

Also append to `.planning/STATE.md`:
- Quick task `quick-260422-vxg` complete. Branch `quick/260422-vxg-cadence-rebalance-7-sub-agents` awaiting merge.
- Key topology shift: 3 interval + 4 cron sub-agents (from prior 6+1). CONTENT_CRON_AGENTS dict-shape.
- Deferred follow-up flagged: Infographics historical-fallback drafter (see 260422-vxg-PLAN.md deferred section).

DO NOT push branch. DO NOT create PR. Orchestrator reviews + merges after user signs off.
</output>
