---
quick_task: 260421-mos
subsystem: scheduler (quotes sub-agent)
tags: [scheduler, apscheduler, cron, quotes, quality-gate, whitelist]
requirements_completed:
  - MOS-01  # sub_quotes daily CronTrigger at 12:00 America/Los_Angeles (moved off IntervalTrigger)
  - MOS-02  # run_text_story_cycle gains max_count + source_whitelist kwargs (no-op for other 4 users)
  - MOS-03  # quotes.py REPUTABLE_SOURCES frozenset + max_count=2 cap + drafter quality gate (reject path)
  - MOS-04  # test coverage — 1 new test_worker test + 3 new test_quotes tests + 4 new test_content_init tests (+8 total)
commits:
  - 4dbeab3  # feat(scheduler): quotes sub-agent → daily 12pm Pacific + reputable whitelist + quality gate (quick-260421-mos)
files_modified:
  - scheduler/worker.py                         # CONTENT_SUB_AGENTS → CONTENT_INTERVAL_AGENTS (6) + CONTENT_CRON_AGENTS (1); CronTrigger import; second registration loop; docstring refresh
  - scheduler/agents/content/__init__.py        # run_text_story_cycle gains max_count + source_whitelist kwargs; whitelist filter + max_count cap inserted between format filter and candidate loop
  - scheduler/agents/content/quotes.py          # REPUTABLE_SOURCES frozenset (27 entries); _draft prompt quality bar + reject path; run_draft_cycle passes max_count=2 + source_whitelist=REPUTABLE_SOURCES
  - scheduler/tests/test_worker.py              # CONTENT_SUB_AGENTS→CONTENT_INTERVAL_AGENTS import rename; lock-id test iterates both lists; new test_quotes_is_daily_cron; offsets list trimmed to [0,17,34,68,85,102] (51 removed with sub_quotes)
  - scheduler/tests/test_quotes.py              # +3 tests: test_reputable_sources_set_populated, test_draft_returns_none_on_reject, test_run_draft_cycle_passes_filters
files_created:
  - scheduler/tests/test_content_init.py        # NEW — 4 tests for run_text_story_cycle filter logic (whitelist, max_count, both no-op paths)
key_decisions:
  - "Split CONTENT_SUB_AGENTS into CONTENT_INTERVAL_AGENTS (6) + CONTENT_CRON_AGENTS (1) rather than adding a discriminator field to the existing tuple — cleaner separation, cron agents carry a different schema (hour/minute/timezone vs offset/interval_hours)."
  - "Whitelist filter runs BEFORE max_count cap so top-N applies over the already-reputable set. Order matters: reversing would give top-2 by recency then filter, often yielding 0-1 candidates when the top-N of all stories happen to be non-whitelisted."
  - "Drafter quality gate: 4-criterion bar (speaker credibility / substance / freshness / clarity) embedded in user_prompt; Claude returns {\"reject\": true, \"rationale\": \"...\"} when no quote in the article meets the bar. Reject path returns None from _draft, which triggers the existing stub-bundle branch in run_text_story_cycle (ContentBundle with compliance_passed=False, no draft_content, no draft_item) — same shape as a JSON parse failure, treated identically downstream."
  - "DST-aware scheduling via timezone=\"America/Los_Angeles\" (not UTC-fixed) — handles PST/PDT transitions automatically, never fires at the wrong wall-clock hour."
  - "max_count/source_whitelist default to None so the 4 other sub-agents using run_text_story_cycle (breaking_news, threads, long_form, infographics) keep identical behavior — opt-in filters."
  - "Executor worktree was at k9z HEAD (aaac399) and had to rebase onto m9k HEAD (3fa7212) before editing since the plan treated m9k's 6-tuple schema + 10s buffer as prerequisite. Post-rebase edits are a single commit on top of m9k."
  - "America/Los_Angeles appears 7 times in worker.py (5 docstring/comment references + 2 code: the tuple entry + the log format string). Plan's validation accepts ≥1 — extra doc mentions are semantically inert."
metrics:
  duration_minutes: 35
  completed_date: "2026-04-21"
  tasks_completed: 1
  test_delta: "74 → 82 (+8)"
---

# Quick Task 260421-mos Summary

Moves the Quotes sub-agent off the 2h interval trigger onto a **daily 12:00 America/Los_Angeles cron trigger**, layers a **reputable-source whitelist** (27 tier-1 financial + gold-specialist + institutional patterns) + **top-2 by recency cap** + **drafter quality gate** (named senior speaker, substance, freshness, clarity) so the noon fire produces 0-2 high-signal quote drafts per day instead of up to 12 per day of mixed-quality output. Zero behavior change for the other 6 sub-agents.

## What Changed

### 1. Scheduler topology — `scheduler/worker.py`

`CONTENT_SUB_AGENTS` (7 entries, all on `IntervalTrigger`) split into two lists to let cron-style and interval-style sub-agents coexist cleanly:

| List | Entries | Schema | Trigger |
|---|---|---|---|
| `CONTENT_INTERVAL_AGENTS` | 6 | `(job_id, run_fn, name, lock_id, offset_minutes, interval_hours)` | `IntervalTrigger(hours=interval_hours, start_date=now+offset+10s)` |
| `CONTENT_CRON_AGENTS` | 1 | `(job_id, run_fn, name, lock_id, hour, minute, timezone)` | `CronTrigger(hour=hour, minute=minute, timezone=tz)` |

- New import: `from apscheduler.triggers.cron import CronTrigger`.
- New second registration loop in `build_scheduler()` for cron agents — registered after the interval loop so startup log reports both counts.
- Startup log line now reads `interval_sub_agents=6 jobs (sub_breaking_news=1h, others=2h), cron_sub_agents=1 jobs (sub_quotes daily 12:00 America/Los_Angeles)`.
- `JOB_LOCK_IDS` unchanged (still 8 keys: morning_digest + 7 sub_* lock IDs 1010-1016). Only the schedule shape moved; `sub_quotes` still holds lock 1013.

### 2. Shared pipeline kwargs — `scheduler/agents/content/__init__.py`

`run_text_story_cycle(...)` gains two optional kwargs, both defaulting to `None`:

```python
max_count: int | None = None
source_whitelist: frozenset[str] | None = None
```

Filter logic inserted INSIDE the existing `try` block, AFTER the `content_type` format filter and BEFORE the `if not candidates:` early-exit — so it runs once per tick, not once per candidate. Whitelist filter runs first (case-insensitive substring match against `story.get("source_name")`), then max_count cap sorts by `story.get("published_at", "")` descending and takes top N. Both filters log stage counts (`before → after, dropped N`) so Railway logs show the funnel clearly.

Defaults = None means the 4 other sub-agents that use this helper (breaking_news, threads, long_form, infographics) skip both filters and behave identically. Verified by `test_source_whitelist_none_is_noop` + `test_max_count_none_is_noop`.

### 3. Quotes wiring + quality gate — `scheduler/agents/content/quotes.py`

Module-level `REPUTABLE_SOURCES: frozenset[str]` with 27 patterns across three tiers:

- **Tier-1 financial:** reuters, bloomberg, wsj, wall street journal, financial times, ft.com, barron, marketwatch, cnbc, economist, financial post.
- **Gold-specialist:** kitco, mining.com, mining journal, mining weekly, northern miner, gold hub.
- **Institutional:** world gold council, wgc, imf, bis.org, federal reserve, european central bank, bank of england, bank of japan, people's bank, s&p global, moody's.

`run_draft_cycle()` wires both filters:

```python
await run_text_story_cycle(
    agent_name=AGENT_NAME,
    content_type=CONTENT_TYPE,
    draft_fn=_draft,
    max_count=2,
    source_whitelist=REPUTABLE_SOURCES,
)
```

`_draft` prompt extended with an explicit **Quality bar** section (4 criteria: speaker credibility — named senior role required, substance — specific number/timeframe/catalyst, freshness — current article only, clarity — self-contained claim) + a reject-path JSON option (`{"reject": true, "rationale": "..."}`). Return logic handles reject before parsing `draft_content` — returns None, which `run_text_story_cycle` treats as the existing stub-bundle path (`ContentBundle` with `compliance_passed=False`, no draft_item attached). Same behavior as a JSON parse failure — no new code paths downstream.

### 4. Test updates

| File | Action | Tests |
|---|---|---|
| `tests/test_worker.py` | Updated | `CONTENT_SUB_AGENTS → CONTENT_INTERVAL_AGENTS` import rename; `test_sub_agents_total_seven` (renamed, asserts `len(INTERVAL) + len(CRON) == 7`); `test_sub_agent_staggering` offsets `[0,17,34,51,68,85,102]` → `[0,17,34,68,85,102]` (51 removed with sub_quotes); `test_sub_agent_lock_ids` iterates both lists; **NEW** `test_quotes_is_daily_cron` asserts lock_id=1013, hour=12, minute=0, timezone="America/Los_Angeles" |
| `tests/test_quotes.py` | Added +3 | `test_reputable_sources_set_populated`; `test_draft_returns_none_on_reject`; `test_run_draft_cycle_passes_filters` |
| `tests/test_content_init.py` | NEW | `test_source_whitelist_filters_stories`; `test_max_count_caps_candidates`; `test_source_whitelist_none_is_noop`; `test_max_count_none_is_noop` |

## Gate Results

| Command | Baseline (m9k) | Post-mos | Delta |
|---|---|---|---|
| `uv run ruff check scheduler/` | clean | clean | ✓ |
| `uv run pytest -x` (scheduler) | 74 passed | **82 passed** | +8 |

All validation greps from the plan pass:

- `grep CronTrigger scheduler/worker.py` → 2 matches (import + instantiation) ✓
- `grep sub_quotes scheduler/worker.py` → 7 matches, all inside `JOB_LOCK_IDS` / `CONTENT_CRON_AGENTS` / docstrings / comments — **zero** inside `CONTENT_INTERVAL_AGENTS` ✓
- `grep America/Los_Angeles scheduler/worker.py` → 7 matches (1 tuple entry + 1 log format + 5 doc/comment references, all inert)
- `grep CONTENT_INTERVAL_AGENTS scheduler/worker.py` → 3 matches (definition + comment reference + loop) ✓
- `grep CONTENT_CRON_AGENTS scheduler/worker.py` → 3 matches (definition + log + loop) ✓
- `grep REPUTABLE_SOURCES scheduler/agents/content/quotes.py` → 2 matches (definition + reference) ✓
- `grep 'max_count=2' scheduler/agents/content/quotes.py` → 1 match (run_draft_cycle call) ✓
- `grep reject scheduler/agents/content/quotes.py` → 3 matches (prompt + parsed-dict check + log line) ✓
- `grep 'source_whitelist\|max_count' scheduler/agents/content/__init__.py` → 13 matches (signature + docstring + filter logic + logs) ✓

## Commits

| SHA | Subject | Files | Net change |
|---|---|---|---|
| `4dbeab3` | `feat(scheduler): quotes sub-agent → daily 12pm Pacific + reputable whitelist + quality gate (quick-260421-mos)` | worker.py, content/__init__.py, content/quotes.py, test_worker.py, test_quotes.py, test_content_init.py (new) | +334 / −24 across 6 files |

`git diff main..HEAD --stat` now shows 6 implementation files + 2 m9k commits + this planning commit (added separately after this SUMMARY was written).

## Deviations from Plan

Three minor, documented in executor's report (GSD Rule 3):

1. **Worktree rebase before editing.** Worktree spawned from k9z HEAD (`aaac399`); plan's "interfaces" section assumed m9k's 6-tuple schema + 10s start_date buffer were in place. Executor ran `git rebase quick/260421-mos-quotes-daily-noon-reputable` to bring the worktree onto m9k HEAD (`3fa7212`) before editing. Single atomic commit (`4dbeab3`) sits cleanly on top of m9k.
2. **`America/Los_Angeles` appears 7 times in worker.py, not 1-2.** Five extra mentions are in docstrings / comments / the startup log format string. All semantically inert and readability-positive. Plan's validation threshold was `≥1`.
3. **Removed unused `MagicMock` import** from the new `test_content_init.py` — ruff flagged it (F401); none of the 4 new tests used it. Kept `AsyncMock, patch` only.

## Operator Follow-up

None — this is a pure scheduler/drafter change, no DB migrations, no frontend touch. On next Railway scheduler redeploy:

1. Startup log should show `interval_sub_agents=6 jobs ... cron_sub_agents=1 jobs (sub_quotes daily 12:00 America/Los_Angeles)` alongside the existing digest line.
2. Job listing (if inspected) should show `Quotes — daily at 12:00 America/Los_Angeles` as the 8th job (morning_digest + 6 interval + 1 cron).
3. First `sub_quotes` fire: the next 12:00 Pacific (today if redeployed before noon PT; otherwise tomorrow). DST-aware — timezone arg handles PST/PDT automatically.
4. On first fire logs will show the funnel stage counts: `reputable filter: N → K (dropped D non-whitelisted sources)` then `max_count cap: trimmed to top 2 by recency`, then either 1-2 quote drafts OR 0 drafts with per-story reject rationale lines (`quotes._draft: story rejected by quality gate — ...`).
5. `/agents/quotes` dashboard page shows the "Pulled from agent run at 12:00 PM · {date}" header once the first run logs, OR stays empty for 24h if no reputable gold-relevant quote met the quality bar that day.
6. `agent_runs` table: exactly 1 row per day with `agent_name='sub_quotes'` (plus the existing hourly `sub_breaking_news` rows from m9k + 2h rows for the other 5).

**Pre-existing pending Quote drafts** in prod DB are left untouched per user instruction — they predate this change and will be approved/rejected manually.

## Self-Check: PASSED

- `.planning/quick/260421-mos-quotes-sub-agent-daily-12pm-pacific-repu/260421-mos-PLAN.md` ✓ (written by gsd-planner)
- `.planning/quick/260421-mos-quotes-sub-agent-daily-12pm-pacific-repu/260421-mos-SUMMARY.md` ✓ (this file)
- Single implementation commit `4dbeab3` on branch `quick/260421-mos-quotes-daily-noon-reputable` ✓
- Scheduler pytest 82/82, ruff clean ✓
- All 9 validation greps pass ✓
- Zero behavior change for breaking_news / threads / long_form / infographics (run_text_story_cycle consumers with kwargs=None) ✓
- `JOB_LOCK_IDS` unchanged — still 8 keys, sub_quotes still 1013 ✓
- No DB schema touches, no Alembic migrations ✓
- Branch NOT pushed to origin (awaiting operator review + merge + Railway deploy) ✓
