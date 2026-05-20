---
phase: 07-weekly-viral-sweeper
plan: 04
subsystem: scheduler
tags: [python, asyncio, anthropic, sqlalchemy, async, pytest, tweepy, cron]

# Dependency graph
requires:
  - phase: 07-weekly-viral-sweeper-02
    provides: fetch_top_x_posts(query, max_results) X-API consumer with quota gate
  - phase: 07-weekly-viral-sweeper-01
    provides: WeeklySweep dual-model + WeeklySweepCard schema row shape contract
provides:
  - async run_weekly_sweeper() orchestrator wiring X ingest -> virality compute -> Sonnet -> weekly_sweeps INSERT
  - _compute_virality(session) reading daily_summaries.raw_sources_jsonb.gold_news[] from last 7 days, ranked by distinct source_name count DESC
  - canonical_url() helper stripping UTM/fbclid/gclid/ref/source/_ga + sorting query + lowercasing host (P10)
  - Sonnet content-angle generation with gold-bull bias system prompt + grounding rule (P8, P14)
  - Insufficient-signal fallback (P15) when len(x_posts) < 3 OR len(viral_stories) < 3
  - Idempotency guard against duplicate fires for same week_start within 60 min (SWEEP-10)
  - Status mapping: completed / partial / failed per spec (SWEEP-11)
  - Manual escape hatch via python -m agents.weekly_sweeper (__main__ block, P13)
affects: [07-05-scheduler-cron-registration, 07-06-frontend-sweeper-card]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Orchestration shape mirrors scheduler/agents/daily_summary.py: idempotency check -> agent_runs INSERT (status='running') -> external work -> status mapping -> output row INSERT -> finally telemetry"
    - "Per-section try/except with per_section_errors list flowed into agent_runs.errors (post-jny pattern)"
    - "JSON-safety: datetime fields in raw_sources_jsonb.x_posts[].created_at converted via .isoformat() before INSERT (mirrors daily_summary.py:204-217)"
    - "Module-level monkeypatch swap (weekly_sweeper.fetch_top_x_posts, weekly_sweeper.AsyncSessionLocal, weekly_sweeper.AsyncAnthropic) for orchestration tests — cleaner than upstream import patches"
    - "SimpleNamespace + MagicMock pattern for _compute_virality tests: fake DailySummary rows with raw_sources_jsonb dict, session.execute returns scalars().all()"

key-files:
  created:
    - scheduler/agents/weekly_sweeper.py
    - scheduler/tests/test_weekly_sweeper.py
  modified: []

key-decisions:
  - "Insufficient-signal path maps to status='completed' (not 'partial') even when x_ingest/virality sections are flagged failed — sparse weeks are a designed fallback (P15), not an error condition. Special-case in status mapping: if insufficient_signal_path AND sections_failed subset of {x_ingest, virality}, status='completed'."
  - "Per-row deduplicate_stories applied BEFORE cross-summary counting in _compute_virality so same URL in same daily_summary row counts once (P9 from Phase 5 cross-ref)."
  - "Virality lookback cutoff computed in Python timedelta (NOT SQL INTERVAL) for cross-DB portability — mirrors daily_summary.py pattern."
  - "JSON-safety conversion of datetime created_at in raw_sources_jsonb done at write time, not in x_ingest.py, so the upstream consumer keeps Python datetime objects available for future analytics."
  - "Test for top-5 cap uses 10 distinctly-worded titles to avoid the SequenceMatcher >= 0.85 title-similarity dedup that deduplicate_stories applies per-row (caught during TDD — adjusted test data, no code change)."

patterns-established:
  - "Pattern 1: When mirroring daily_summary.py orchestration, the failure path must (a) write a failure WeeklySweep row with raw_sources_jsonb={'error': error_text}, (b) update agent_runs in finally with combined per-section errors, (c) catch and log a secondary exception around the failure-row write."
  - "Pattern 2: Manual escape hatch lives as `if __name__ == '__main__': asyncio.run(...)` at the bottom of any module that needs Sunday-after-deploy invocability (P13). Same pattern can be replicated for any future Sunday/Monday cron with a Railway deploy timing risk."

requirements-completed: [SWEEP-06, SWEEP-07, SWEEP-08, SWEEP-10, SWEEP-11]

# Metrics
duration: 5min
completed: 2026-05-19
---

# Phase 7 Plan 04: Weekly Sweeper Orchestrator + Sonnet Content-Angle Generation Summary

**Async run_weekly_sweeper orchestrating X ingest -> virality compute -> Sonnet content angles -> weekly_sweeps INSERT, with idempotency guard, insufficient-signal fallback, status mapping (completed/partial/failed), and a python -m agents.weekly_sweeper escape hatch — 14 pytest cases covering canonical_url, virality compute, happy path, insufficient signal, Sonnet failure, and idempotency skip, all passing.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-19T05:14:36Z
- **Completed:** 2026-05-19T05:18:40Z
- **Tasks:** 3
- **Files created:** 2 (1 agent module, 1 test file)
- **Files modified:** 0

## Accomplishments

- **Orchestrator landed.** `scheduler/agents/weekly_sweeper.py` exports `async run_weekly_sweeper()` that mirrors `daily_summary.py` shape: idempotency check -> `agent_runs` INSERT (status='running') -> X recent-search ingest -> virality compute over last 7 days of `daily_summaries.raw_sources_jsonb.gold_news[]` -> Sonnet content-angle generation (or P15 insufficient-signal fallback) -> status mapping -> `weekly_sweeps` row INSERT -> finally telemetry update.
- **All 9 cited pitfalls defended.** P3 (NULL raw_sources_jsonb guard), P6 (AsyncAnthropic timeout=60.0), P7 (X post text [:500] before Sonnet), P8 (gold bull bias system prompt), P10 (canonical_url strips UTM/fbclid/gclid/ref/source/_ga + sorts + lowercases), P12 (~25s expected runtime well under 30-min stale-run threshold), P13 (`__main__` block + docstring), P14 (Sonnet grounding rule "use ONLY facts present in supplied inputs"), P15 (insufficient-signal fallback when `len(x_posts) < 3 OR len(viral_stories) < 3`).
- **Status mapping per SWEEP-11.** `completed` when all 3 sections succeed OR the insufficient-signal designed-fallback path executes; `partial` when at least one section unexpectedly fails but the row can still render; `failed` only on a catastrophic exception that prevents any markdown assembly.
- **Idempotency guard locked.** 60-min window check against existing rows with matching `week_start` AND `status IN ('running','completed')` — exits cleanly before any side effects when a recent fire already wrote a row (defends against APScheduler misfire double-fires).
- **Manual escape hatch wired.** `if __name__ == "__main__": asyncio.run(run_weekly_sweeper())` at the bottom of the module + clear docstring documentation. P13 mitigated: a Railway deploy landing after Sunday 08:30 PT can still recover the week via `python -m agents.weekly_sweeper` from the Railway shell.
- **Test pass count: 14/14.** Test suite covers canonical_url (5: tracking strip, query sort, trailing slash, lowercase host, full strip set), _compute_virality (5: empty DB, NULL guard, ranking by distinct sources, top-5 cap, canonicalization grouping), and run_weekly_sweeper (4: happy path, insufficient signal, Sonnet failure, idempotency skip). Joint suite with `test_x_ingest.py` runs 23 tests, all green.

## Orchestration Call Graph

```
run_weekly_sweeper()
├─ datetime.now(timezone.utc)  → now_utc
├─ _sunday_of_this_week(now_utc)  → sunday (LA-tz date)
│
├─ AsyncSessionLocal() as session:
│  └─ _idempotency_skip(session, now_utc)
│     └─ SELECT WeeklySweep.id WHERE week_start = sunday
│           AND generated_at >= now - 60min
│           AND status IN ('running','completed') LIMIT 1
│     → if hit: log "idempotency_skip" + RETURN
│
├─ AgentRun(agent_name='weekly_sweeper', status='running', started_at=now_utc) → INSERT + refresh
│
├─ AsyncAnthropic(api_key=..., timeout=60.0)  ← P6
│
├─ try:
│  ├─ Section 1: fetch_top_x_posts(X_SEARCH_QUERY, max_results=100)  ← 07-02
│  │  └─ _build_x_posts_md(x_posts)
│  │
│  ├─ Section 2: AsyncSessionLocal() as session: _compute_virality(session)
│  │  ├─ SELECT DailySummary WHERE generated_at >= now-7d AND status IN ('completed','partial')
│  │  ├─ For each row: P3 guard → deduplicate_stories(stories) → canonical_url(link)
│  │  ├─ Group by canonical_url, count distinct source_name
│  │  └─ Sort by distinct_source_count DESC, take top 5
│  │  └─ _build_virality_md(viral_stories)
│  │
│  ├─ Section 3: P15 branch
│  │  ├─ if len(x_posts) < 3 OR len(viral_stories) < 3:
│  │  │     angles_md = INSUFFICIENT_SIGNAL_FALLBACK
│  │  │     insufficient_signal_path = True
│  │  └─ else: _call_sonnet_for_angles(x_posts, viral_stories, anthropic_client)
│  │     ├─ Build user prompt with X posts ([:500] truncation per P7)
│  │     ├─ messages.create(model='claude-sonnet-4-6', max_tokens=1000, system=SONNET_SYSTEM_PROMPT)
│  │     └─ return response.content[0].text.strip()  (None on exception)
│  │
│  ├─ Status mapping (SWEEP-11):
│  │   insufficient_signal_path AND sections_failed ⊆ {x_ingest, virality} → 'completed'
│  │   not sections_failed                                                  → 'completed'
│  │   any markdown assembled                                               → 'partial'
│  │   otherwise                                                            → 'failed'
│  │
│  └─ AsyncSessionLocal() as session: WeeklySweep(week_start, week_end, ...) → INSERT
│
├─ except Exception:
│  └─ Write WeeklySweep failure row with raw_sources_jsonb={'error': error_text}
│
└─ finally:
   └─ session.get(AgentRun, id) → update status, ended_at, items_*, notes (JSON), errors (combined)
```

## SONNET_SYSTEM_PROMPT — First Paragraph

> "You are a tactical content strategist for a senior gold-sector analyst. The audience is a gold-focused social media account whose voice is data-driven, Bloomberg commodities-desk energy. You generate exactly 3 content angles each week, each connecting an X (Twitter) signal from the gold conversation with a mainstream news signal that the operator's audience is also seeing this week."

Subsequent paragraphs enforce: gold bull thesis bias (P8 — "Reframe bearish-leaning X chatter through the bull lens... or DISCARD"), grounding rule (P14 — "Use ONLY facts, figures, claims, and source names present in the supplied inputs"), and exact markdown structure for the 3 angles (Hook + 3 Bullets each: X signal, News signal, Bull connection).

## Status Mapping Logic (SWEEP-11)

| Condition                                                                  | Resulting Status |
| -------------------------------------------------------------------------- | ---------------- |
| All 3 sections succeed                                                     | `completed`      |
| Insufficient signal path AND sections_failed ⊆ {x_ingest, virality}        | `completed`      |
| At least one section failed unexpectedly but x_md/virality_md/angles_md present | `partial`   |
| No markdown could be assembled at all                                      | `failed`         |
| Catastrophic exception during the try block                                | `failed` (failure row written) |

The insufficient-signal carve-out is the key non-obvious branch: when the week is sparse (fewer than 3 X posts OR fewer than 3 viral stories), the Sonnet call is deliberately skipped and `content_angles_md` gets the canned "Insufficient signal this week — angles not generated" copy. This is a designed fallback per P15, NOT a failure condition, so it maps to `completed` even though `x_ingest` and/or `virality` may technically be in `sections_failed`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Module shell — constants, canonical_url, _compute_virality** — `e482f79` (feat)
2. **Task 2: Append run_weekly_sweeper orchestrator + Sonnet call + status mapping + __main__** — `42a2991` (feat)
3. **Task 3: pytest coverage — 14 tests across all 3 control-flow surfaces** — `083f816` (test)

## Files

**Created:**
- `scheduler/agents/weekly_sweeper.py` — 533 lines (well over the 200-line min_lines spec). Exports `run_weekly_sweeper`, `canonical_url`, `_compute_virality`, `_idempotency_skip`, `_sunday_of_this_week`, `_build_x_posts_md`, `_build_virality_md`, `_call_sonnet_for_angles`, `SONNET_SYSTEM_PROMPT`, `INSUFFICIENT_SIGNAL_FALLBACK`, plus locked constants.
- `scheduler/tests/test_weekly_sweeper.py` — 14 pytest cases.

## Verification Run

```
cd scheduler && uv run pytest tests/test_weekly_sweeper.py -q
..............                                                           [100%]
14 passed in 0.32s

cd scheduler && uv run pytest tests/test_x_ingest.py tests/test_weekly_sweeper.py -q
.......................                                                  [100%]
23 passed in 0.33s
```

All plan-level verification checks (1-7) PASS:
1. `from agents.weekly_sweeper import run_weekly_sweeper` — exit 0
2. `pytest tests/test_weekly_sweeper.py -q` — 14/14 pass
3. `pytest tests/test_x_ingest.py tests/test_weekly_sweeper.py -q` — 23/23 pass
4. `timeout=SONNET_TIMEOUT_S` present (P6)
5. `claude-sonnet-4-6` present (model locked)
6. `python -m agents.weekly_sweeper` present in docstring (P13 escape hatch)
7. No `asyncpraw` / `praw` / `REDDIT_` leakage in module or tests (pivot enforced)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_compute_virality_top_5_only collapsed to 1 story instead of 5**

- **Found during:** Task 3 verification run
- **Issue:** The original test seeded 10 stories with titles "Story 0" through "Story 9". These titles are similar enough that `deduplicate_stories` (called inside `_compute_virality` per the P9 per-row dedup contract) collapsed them via SequenceMatcher >= 0.85, leaving only 1 unique title.
- **Fix:** Replaced the 10 "Story {i}" titles with 10 distinctly-worded gold-sector headlines that survive the SequenceMatcher dedup. Comment in the test explains the constraint. No code change — the production behavior is correct (per-row dedup is by design per Phase 5 cross-ref P9), the test fixture was wrong.
- **Files modified:** `scheduler/tests/test_weekly_sweeper.py` (test fixture only)
- **Commit:** `083f816` (single commit for Task 3, fix baked in)

No other deviations. Plan executed exactly as written.

## Known Stubs

None. The orchestrator is fully wired:
- `fetch_top_x_posts` from 07-02 (real implementation)
- `_compute_virality` reads real `daily_summaries` rows
- Sonnet call uses real `AsyncAnthropic` client with locked model + timeout + max_tokens
- WeeklySweep row INSERT against real `weekly_sweeps` table

The cron registration into `worker.py` is the next plan (07-05) — this plan's orchestrator is callable both via that future cron AND directly via `python -m agents.weekly_sweeper` for verification before Sunday.

## Self-Check: PASSED

- FOUND: scheduler/agents/weekly_sweeper.py (533 lines)
- FOUND: scheduler/tests/test_weekly_sweeper.py
- FOUND commit: e482f79 (Task 1)
- FOUND commit: 42a2991 (Task 2)
- FOUND commit: 083f816 (Task 3)
