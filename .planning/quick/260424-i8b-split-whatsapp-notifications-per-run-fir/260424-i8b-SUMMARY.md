---
task: 260424-i8b
type: quick
shipped: 2026-04-24
outcome: "sub_breaking_news and sub_threads now fire a per-run WhatsApp listing all approved items; the daily digest was retimed to 12:30 PT and runtime-filtered (via senior_agent._assemble_digest) to the 4 non-firehose agents."
commits:
  - hash: 9c783f0
    message: "feat(scheduler): WhatsApp firehose per-run + midday digest split + digest filter (i8b)"
    note: "T1+T2 combined per plan allowance"
tests_run: 166
ruff: clean
---

# Quick Task 260424-i8b: Split WhatsApp notifications (firehose + midday digest) — Summary

## Outcome

sub_breaking_news and sub_threads now fire a per-run WhatsApp listing all approved items; the daily digest was retimed to 12:30 PT and runtime-filtered (via senior_agent._assemble_digest) to the 4 non-firehose agents.

## Date Shipped

2026-04-24

## Files Modified

### Source files (4)
- `scheduler/services/whatsapp.py` — added `build_chunks()` (greedy pack, 1500-char budget, single-chunk no prefix, multi-chunk `[short X/N]` prefix on every chunk) and `send_agent_run_notification()` async dispatcher.
- `scheduler/worker.py` — renamed `morning_digest` → `midday_digest` (job id + JOB_LOCK_IDS, lock ID 1005 unchanged); retimed CronTrigger 07:00 → 12:30 America/Los_Angeles; declared `DIGEST_EXCLUDED_CONTENT_TYPES = frozenset({"breaking_news", "thread"})`; wired constant into `SeniorAgent(excluded_content_types=...)` in `_make_midday_digest_job` factory.
- `scheduler/agents/senior_agent.py` (NARROW-DIFF) — added `excluded_content_types: frozenset[str] | None = None` kwarg to `SeniorAgent.__init__`; added `ContentBundle` import; built `_firehose_exists_subq` NOT EXISTS subquery and applied `.where(~_firehose_exists_subq)` to all 4 DraftItem queries in `_assemble_digest` (approved, rejected, expired, top_stories). Guard: empty frozenset skips filter entirely for back-compat.
- `scheduler/agents/content/__init__.py` — added `from services import whatsapp` import; added `_persisted_items: list[str] = []` accumulator; appended tweet/thread text after `items_queued += 1` for firehose agents; inserted per-run dispatch block after `agent_run.status = "completed"` with JSON-merge into `agent_run.notes` (never string-concat); Twilio failures are silent-continue.

### Test files (4)
- `scheduler/tests/test_whatsapp.py` — 8 new tests: single-chunk no prefix, multi-chunk prefix format, never-split-item, 1500-char budget, short name stripping, dispatch order, empty items short-circuit, creds-missing early stop.
- `scheduler/tests/test_worker.py` — 4 new tests + updated 3 existing tests to reflect midday_digest rename: midday_digest CronTrigger at 12:30 PT, lock ID 1005 preserved, DIGEST_EXCLUDED_CONTENT_TYPES frozenset, SeniorAgent wiring. Updated: test_retired_crons_absent_from_job_lock_ids, test_scheduler_registers_7_jobs, test_morning_digest_cron_fires_in_pacific_time.
- `scheduler/tests/test_senior_agent.py` — 1 new test: test_assemble_digest_excludes_firehose_content_types verifies SQL has ContentBundle subquery filter and digest returns only non-firehose item counts.
- `scheduler/tests/test_content_wrapper.py` (new file) — 6 new tests: hook fires for breaking_news/threads with items_queued > 0, hook skipped for other agents, hook skipped when items_queued == 0, Twilio failure is silent (status='completed', JSON notes has whatsapp_per_run_failed + candidates), happy-path merges whatsapp_per_run_sent into JSON notes.

## Commits Landed

| Commit | Message | Scope |
|--------|---------|-------|
| 9c783f0 | feat(scheduler): WhatsApp firehose per-run + midday digest split + digest filter (i8b) | T1+T2 combined |

T3 (docs): this SUMMARY + STATE row update.

## Verification Snapshot

```
pytest: 166 tests, 0 failures, 0 errors (55 pre-existing warnings — unawaited coroutines in mock setup, unrelated to this task)
ruff check .: All checks passed
```

### Grep sanity checks (all matched)

```
grep -n "hour=12" scheduler/worker.py          # L321, L351
grep -n "minute=30" scheduler/worker.py        # L321, L352
grep -n "midday_digest" scheduler/worker.py    # L7, L32, L96, L224-241, L310-355
grep -n "DIGEST_EXCLUDED_CONTENT_TYPES"        # L8, L33, L77, L231, L237, L311, L346
grep -n "send_agent_run_notification"          # whatsapp.py L157, content/__init__.py L392
grep -n "def build_chunks"                     # whatsapp.py L109
grep -n "whatsapp_per_run"                     # content/__init__.py L398-409
grep -n "excluded_content_types"               # senior_agent.py L36, L41
grep -n "content_type"                         # senior_agent.py L113-119
```

## Preservation Confirmed

### ZERO DIFF (git diff main -- <path> is empty)
- `scheduler/agents/content/breaking_news.py` — VERIFIED EMPTY
- `scheduler/agents/content/threads.py` — VERIFIED EMPTY
- `scheduler/agents/content/quotes.py` — VERIFIED EMPTY
- `scheduler/agents/content/infographics.py` — VERIFIED EMPTY
- `scheduler/agents/content/gold_media.py` — VERIFIED EMPTY
- `scheduler/agents/content/gold_history.py` — VERIFIED EMPTY
- `scheduler/agents/content_agent.py` — VERIFIED EMPTY
- `backend/`, `frontend/`, `alembic/`, `scheduler/models/` — VERIFIED EMPTY

### NARROW-DIFF (scheduler/agents/senior_agent.py)
Only permitted changes present:
1. `+from models.content_bundle import ContentBundle` — new import for Path A subquery
2. `def __init__(self) -> None` → `def __init__(self, excluded_content_types: frozenset[str] | None = None) -> None` — new kwarg
3. `+ self._excluded_content_types: frozenset[str] = excluded_content_types or frozenset()` — assignment
4. `+ _firehose_exists_subq = None` / `+ if self._excluded_content_types:` / subquery construction — filter setup
5. `+ if _firehose_exists_subq is not None: _approved_q = _approved_q.where(~_firehose_exists_subq)` (×4 — for approved, rejected, expired, top_stories queries)
6. Query construction refactored from direct `await session.execute(...)` to `_q = (...)\n_q = _q.where(...)\nresult = await session.execute(_q)` shape — minimal structural change needed to apply the conditional filter.

NO other lines changed: `run_morning_digest`, WhatsApp template body, `_headline_from_rationale`, `_get_config`, `seed_senior_config`, `DailyDigest` write, per-agent send pattern at L294, try/except structure — all untouched.

## Implementation Decisions

- **Schema path chosen:** Path A (DraftItem.source_url == ContentBundle.story_url NOT EXISTS subquery). Verified: `content_agent.build_draft_item` sets `DraftItem.source_url = ContentBundle.story_url` at `content_agent.py:674`.
- **T1+T2 combined:** Plan explicitly allowed this; ceremony cost was judged low-value for this quick task. TDD order preserved (test code written before implementation code in same session).
- **Function name kept:** `run_morning_digest` retained per PLAN.md "keep function names" directive. Job id renamed (APScheduler-visible) without touching the Python function name.
- **`_read_schedule_config` retained but result discarded:** Kept for startup-time DB connectivity check; `morning_digest_schedule_hour` value no longer consumed (midday digest time is hardcoded at 12:30 PT, not DB-configurable post-i8b).

## Follow-ups (NOT in scope — intentionally deferred)

- Phase B: approve → auto-post-to-X (tweepy.Client.create_tweet + OAuth 1.0a)
- `draft_items.approval_state` state machine + Alembic migration
- Backend API endpoint + frontend approve button
- Meta WhatsApp Business verification (sandbox 24h session window)
- Digest body prefix tweak: `📊 Morning Digest` → time-neutral prefix (deferred)
- `run_morning_digest` → `run_midday_digest` rename (not required; test passes on job id)
